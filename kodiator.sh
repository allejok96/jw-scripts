#!/bin/bash -x

#
# kodiator
#
# Kräver: egrep, GNU sed, curl
#
# Läs in "Mediator"-filerna från jw.org och processera dem så vi får en
# trädstruktur bestående av variabler och vektorer (arrays).
#
# Något i den här stilen:
#
# 1 = (media video)
# 1_video = (hundvideo kattvideo)
# 1_video_hundvideo = (url namn)
# 1_video_hundvideo_url = "http://www.hundvideo.se/video.mp4"
#
# Sedan läser vi denna trädstruktur och skapar STRM-filer uppsorterade
# i kataloger så Kodi kan läsa dem
#
# Samtidigt följer vi, laddar hem och bearbetar på samma sätt de filer som
# hänvisas till i respektive Mediator-fil
#

cleanup()
{
    if (( CLEANUP )); then
        [[ -e /tmp/.kodiator ]] && rm "${temp_file}"
        [[ -e /tmp/.kodiator.history ]] && rm "${history_file}"
    fi
}

error()
{
    echo "Ett fel har inträffat" 2>&1
    cleanup
    exit 1
}

show_help()
{
    cat<<EOF
Indexera tv.jw.org och spara videolänkarna i STRM-filer.

Användning: kodiator [alternativ] [nyckel] [katalog]
  --no-recursive        Hämta inte automatiskt de filer som hänvisas till
                        i mediatorfilerna
  --no-cleanup          Ta inte bort tempfiler
  nyckel                Namn på mediatorfil att ladda hem
  katalog               Katalog att spara STRM-filerna i
EOF
    exit
}

unsquash_file()
{
    # Läser från stdin

    # Lägg nyrad efter , {} och [] men för inte citat
    # Ta bort allt utom rader med name: key: progressiveDownloadURL: title:
    # eller label:. Behåll även tecken {}[] och rader som slutar på { eller [

    sed -n '
    # Om raden endast består av {} [] eller är tom - hoppa över
    # OBS om vi inte gör detta kommer vi skapa oändligt många nyrader efter
    # det här tecknet
    /^[][{}]\?\n/ {
        # Skriv ut fram till nyrad
        P
        # Börja om på nästa rad
        D
    }

    # Lägg till nyrad efter {} [] och ,
    #  ^                   Början på raden
    # [^]["{},]*           Valfritt antal tecken, inga specialtecken/citat
    #                      OBS! ] måste stå först i [listan]
    # "[^"]*"              Ett "citat" (innehåller själv inga ")
    # \(  -"-  \)*         Valfritt antal citat
    # \(  -"-  \)*         Valfritt antal inte-citat följt av citat
    # &\n                  Ersätt med sig själv + nyrad (lägg till nyrad)
    s/^\([^]["{},]*\("[^"]*"\)*\)*[][{},]/&\n/

    # Lägg avslutande paranteser på egen rad
    # ^.*          Massa tecken i början (nödvändigt?)
    # \([]}]\)     Kom ihåg parantesen
    # \n           Följt av nyrad (slut på raden)
    # \n\1\n       Ersätt med nyrad parantes nyrad
    s/^.*\([]}]\)\n/\n\1\n/

    # Ta bort oviktiga rader
    # ^                  Början på rad
    # "\( ... \)"        Ett citat med någon av strängarna nedan
    # :                  Följt av :
    # \|                 ... eller ...
    # [][{}]\n           Ett specialtecken i slutet av raden
    # !D                 Ta bort om raden INTE matchade
    /^"\(name\|key\|progressiveDownloadURL\|title\|label\)":\|[][{}]\n/ !D

    # Ta bort avslutande komman
    s/,\n/\n/

    # Skriv ut texten fram till nyraden
    P

    # Ta bort texten fram till nyraden och börja om med texten efter nyraden
    D
    '
}

parse_lines()
{
    # Läser från stdin
    # Argument: VEKTORNAMN
    # OSB! VEKTORNAMN får absolut inte innehålla : eller mellanslag.

    # Vi börjar med att flytta oss in i "root-vektorn"
    array_now=${1}

    while read line; do
        case "${line}" in
            \{|\[)
                # Skapa ny "undervektor", utan namn
                new_sub_array
                ;;
            *:\{|*:\[)
                # Skapa "undervektor"
                new_sub_array ${line%:*}
                ;;
            *\}|*\])
                # Vi flyttar oss en vektor "uppåt"
                array_now=${array_now%_*}
                ;;
            *:*)
                # Spara variabel
                new_variable ${line%%:*} "${line#*:}"
                ;;
        esac
    done
}

new_sub_array()
{
    # Argument: "VARIABEL"

    # Ta bort citationstecken och understreck
    sub_array=${1//\"/}
    sub_array=${sub_array//_/UNDERSCORE}

    # Kolla om vi har ett variabelnamn
    if [[ -z ${sub_array} ]]; then
        # Ge variabeln en slumpmässig siffra som namn
        # (fortsätt tills den är oanvänd)
        sub_array=$RANDOM
        while declare -p ${array_now}_${sub_array} &>/dev/null; do
            sub_array=$RANDOM
        done
    fi

    # Lägg till "undervektor"
    eval "${array_now}+=($sub_array)"
    # Vi flyttar oss in i den
    array_now=${array_now}_${sub_array}
}

new_variable()
{
    # Argument: "VARIABEL" "VÄRDE"
    #           "VARIABEL" VÄRDE

    # Ta bort citationstecken
    variable=${1//\"/}
    value="${2//\"/}"

    # Ta bort understreck ur variabelnamn
    variable=${variable//_/UNDERSCORE}

    # Lägg till variabeln i nuvarande vektor
    eval ${array_now}'+=('${variable}')' || error
    # Ge variabeln ett värde
    eval ${array_now}_${variable}'="'${value}'"' || error
}

recursive_read()
{
    # Argument: KATALOG VEKTOR UNDERVEKTORER ...

    # Nuvarande katalog i filsystemet
    dir_now="${1}"
    dir_next="${dir_now}"
    shift

    # Nuvarande vektor
    array_now=${1}
    shift

    # Spara viktiga variabler (från "undervariabler")

    # Avgör om vi ska skriva filer, skapa mappar eller hämta fler webbsidor
    #
    # [0-9_]*            Bottenstreck och siffror i slutet av raden
    # //                 Ta bort dem
    #
    # ^.*_               Alla tecken fram till sista bottenstreck
    # //                 Ta bort dem
    case $(echo $array_now | sed 's/[0-9_]*$//; s/^.*_//') in
        category|subcategories|media)

            # Använd name eller title som mappnamn, beroende på vilken som finns
            name="$(eval 'echo ${'${array_now}'_name}')"
            title="$(eval 'echo ${'${array_now}'_title}')"
            sub_dir="${name:-${title}}"
            # Ta bort ev. snedstreck
            sub_dir="${sub_dir//\//}"

            if [[ ${sub_dir} ]]; then
                # Skapa mappen
                if [[ ! -e "${dir_now}/${sub_dir}" ]]; then
                    mkdir -p "${dir_now}/${sub_dir}" || error
                fi
                # Den katalog vi ska gå ner i, nästa gång
                dir_next="${dir_now}/${sub_dir}"
            fi

            # URL till annan mediator-fil
            url_next="$(eval 'echo ${'${array_now}'_key}')"
            if [[ ${url_next} ]] && ((RECURSIVE)); then
                # Starta ny instans av kodiator och peka den på en annan URL
                # (ta inte bort filen med URL-historik)
                "$0" --no-cleanup "${dir_now}" "${url_next}"
            fi

            ;;

        files)

            # URL till video
            link="$(eval 'echo ${'${array_now}'_progressiveDownloadURL}')"
            # Filnamn att spara länken i (ta bort ev. snedstreck)
            file_name="$(eval 'echo ${'${array_now}'_label}')"
            file_name="${file_name//\//}"
            # Skapa filen
            if [[ ${file_name} && ${link} ]]; then
                echo "${link}" > "${dir_now}/${file_name}.strm" || error
            fi
            ;;

        images)
            # Hoppa över allt innehåll i "images"
            return
            ;;
    esac

    # Gå igenom "undervektorerna"
    for sub_array in "$@"; do

        # Strunta i tomma variabler (annars blir declare arg)
        [[ -z $(eval 'echo ${'${array_now}_${sub_array}'}') ]] && continue

        # Kolla om det är en vektor
        if declare -p ${array_now}_${sub_array} | egrep -q '^declare -a'; then

            # Gör om denna funktion på varje "undervektor"
            # OBS! Gör i underprocess så den inte kan påverka våra variabler
            eval '(recursive_read \
                "${dir_next}" \
                ${array_now}_${sub_array} \
                ${'${array_now}_${sub_array}'[@]}\
                )' || error
        fi
    done
}


##### INSTÄLLNINGAR


# Städa upp om vi avslutas
trap cleanup SIGINT SIGTERM SIGHUP

# Inställningar
RECURSIVE=1
CLEANUP=1

# Argument
[[ $1 = --help ]] && show_help
[[ $1 = --no-recursive ]] && RECURSIVE=0 && shift
[[ $1 = --no-cleanup ]] && CLEANUP=0 && shift

dir_root="${1:-/tmp/kodiator}"

url_root="http://mediator.jw.org/v1/categories/E/"
url_sub="${2:-VideoOnDemand}"
url_suffix="?detailed=1"

history_file="/tmp/.kodiator.history"
temp_file="/tmp/.kodiator.tmp"
array_root="kodiator_${url_sub}"


##### HUVUD


# Bearbeta inte filer som redan bearbetats
[[ -e ${history_file} ]] && egrep -q "^${url_sub}$" "${history_file}" && exit
# Lägg till i historiken
echo "${url_sub}" >> "${history_file}"

# Ladda hem filen och behandla filen
# OBS! Här används en pipe. Kommandon som pipeas ihop körs i en underprocess.
# Vi kan inte spara variabler när vi kör i en underprocess.
# Därför dumpar vi utdatat till en fil och låter parse_lines() skapa variabler
# lite senare.
curl "${url_root}${url_sub}${url_suffix}" | unsquash_file > "${temp_file}" || error

# Bearbeta och spara alla värden i variabler
parse_lines ${array_root} < "${temp_file}" || error

# Läs igenom alla variabler och skapa kataloger med STRM-filer
eval 'recursive_read \
    "${dir_root}" \
    ${array_root} \
    ${'${array_root}'[@]}\
    ' || error

cleanup
