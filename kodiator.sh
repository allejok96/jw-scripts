#!/bin/bash
#
# kodiator
#
# Requires: egrep, GNU sed, curl
#
# Index tv.jw.org by processing the files from mediator.jw.org
# and create a hirarchy of variables and arrays. Then read that
# hirarchy and create directories containing .strm files (which
# is text file with URLs that Kodi can open).
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
    echo "${@:-Something went wrong, exiting}" 1>&2
    cleanup
    exit 1
}

show_help()
{
    cat<<EOF
Index tv.jw.org and save the video links in .strm files

Usage: kodiator [options] [KEY] [DIRECTORY]
  --lang LANGUAGE       Language to download. Selecting no language
                        will show a list of available language codes
  --no-recursive        Just download this file
  --no-cleanup          Keep temporary files
  KEY                   Name of the file to download and process
  DIRECTORY             Directory to save the .strm files in

  
EOF
    exit
}

unsquash_file()
{
    # Reads on stdin

    # Add newline after , {} and [] but not inside quotes
    # Remove all lines but the ones containing name: key:
    # progressiveDownloadURL: title: or label:
    # Also keep the characters {}[] and lines ending with { or [

    sed '

# Add a newline after all "special" characters
s/[][{},]/&\n/g

' | sed -n '

: start

# Does this row have an uneven number of citation marks
# - that means that the quote continues on the next line
/^\([^"\n]*"[^"\n]*"\)*[^"\n]*"[^"\n]*$/ {

# Append the next line of input
N

# Remove the newline between the two input lines
s/\n//g

# Go back to start
# (Test the line again)
b start
}

# If the line is OK, print it
p

' | sed '

# Remove all ending commas
s/,$//
'
}

parse_lines()
{
    # Reads on stdin
    # Arguments: ARRAY
    # Note: ARRAY must NOT contain any spaces or :

    # Start by going into the "root array"
    array_now=${1}

    while read line; do
        case "${line}" in
            \{|\[)
                # Create new "sub array", without name
                new_sub_array
                ;;
            *:\{|*:\[)
                # Create new "sub array"
                new_sub_array "${line%:*}"
                ;;
            *\}|*\])
                # We go "up" one array
                array_now=${array_now%_*}
                ;;
            *:*)
                # Save variable
                new_variable "${line%%:*}" "${line#*:}"
                ;;
        esac
    done
}

new_sub_array()
{
    # Arguments: "VARIABLE"

    # Remove quotations marks and underscores
    sub_array=${1//\"/}
    sub_array=${sub_array//_/UNDERSCORE}

    # Check if it has a name
    if [[ -z ${sub_array} ]]; then
        # Give the variable a random name
        # (repeat til we find a free one)
        sub_array=$RANDOM
        while declare -p ${array_now}_${sub_array} &>/dev/null; do
            sub_array=$RANDOM
        done
    fi

    # Add new "sub array"
    eval "${array_now}+=($sub_array)"
    # We go in to it
    array_now=${array_now}_${sub_array}
}

new_variable()
{
    # Arguments: "VARIABLE" "VALUE"
    #            "VARIABLE" VALUE

    # Remove quotations marks
    variable=${1//\"/}
    value="${2//\"/}"

    # Remove underscore from the variable name
    variable=${variable//_/UNDERSCORE}

    # Add the variable to the current array
    eval "${array_now}"'+=('"${variable}"')' || error
    # Give the variable a value
    eval "${array_now}_${variable}"'="'"${value}"'"' || error
}

recursive_read()
{
    # Arguments: DIRECTORY ARRAY SUB-ARRAYS ...

    # Current directory in the filesystem
    dir_now="${1}"
    dir_next="${dir_now}"
    shift

    # Current array
    array_now=${1}
    shift

    # Save important variables (from "sub arrays")

    # Decide if we should write files, create dirs or download files
    #
    # [0-9_]*$           Underscores and numbers in the end of the line
    # //                 Remove them
    #
    # ^.*_               All characters until the last underscore
    # //                 Remove them
    case "$(printf '%s\n' "$array_now" | sed 's/[0-9_]*$//; s/^.*_//')" in
        category|subcategories|media)

            # Use "name" or "title" as direcotry name, depending on which there
            name="$(eval 'echo ${'"${array_now}"'_name}')"
            title="$(eval 'echo ${'"${array_now}"'_title}')"
            sub_dir="${name:-${title}}"
            # Remove underscores, if any
            sub_dir="${sub_dir//\//}"

            if [[ ${sub_dir} ]]; then
                # Create the directory
                if [[ ! -e "${dir_now}/${sub_dir}" ]]; then
                    mkdir -p "${dir_now}/${sub_dir}" || error
                fi
                # The dir to move into, next round
                dir_next="${dir_now}/${sub_dir}"
            fi

            # URL to another mediator-file
            url_next="$(eval 'echo ${'"${array_now}"'_key}')"
            if [[ ${url_next} ]] && ((RECURSIVE)); then
                # Start new instance of kodiator and point it to the other URL
                # (do not remove the files with URL history)
                "$0" --no-cleanup "${dir_now}" "${url_next}" || echo "$url_sub: Continuing"
            fi

            ;;

        files)

            # Video URL
            link="$(eval 'echo ${'"${array_now}"'_progressiveDownloadURL}')"
            # File to save the link in (remove underscores, if any)
            file_name="$(eval 'echo ${'"${array_now}"'_label}')"
            file_name="${file_name//\//}"
            # Create the file
            if [[ ${file_name} && ${link} ]]; then
                echo "${link}" > "${dir_now}/${file_name}.strm" || error
            fi
            ;;

        images)
            # Skip all contens of "images"
            return
            ;;
    esac

    # Process the "sub arrays"
    for sub_array in "$@"; do

        # Skip empty variables (or declare will get upset)
        [[ -z $(eval 'echo ${'"${array_now}_${sub_array}"'}') ]] && continue

        # Check if it is an array
        if declare -p ${array_now}_${sub_array} | egrep -q '^declare -a'; then

            # Repeat this for every "sub array"
            # Note: Do this in a sub-shell so that our current variables
            # will stay unaffected
            eval '(recursive_read \
                "${dir_next}" \
                ${array_now}_${sub_array} \
                ${'"${array_now}_${sub_array}"'[@]}\
                )' || error
        fi
    done
}

lang_check()
{
    # Arguments: LANGUAGE
    (
        curl --silent "$lang_list_url" || error "Unable to download language list"
    ) | egrep -q '"code":"'"$1"'"'
}

lang_list()
{
    # Make the language list readable
    # Note: This is probably not very failsafe
    #
    # sed 1:
    # Make newline at every opening bracket
    # where a new language starts
    #
    # sed 2:
    # Replace "name":"LANG" ... "code":"CODE"
    # with LANG CODE
    #
    # Sort it
    #
    # sed 3:
    # Switch LANG with CODE and vice versa
    #
    # Make a nice list with columns

    curl --silent "$lang_list_url" \
        | sed 's/{/\n/g' \
        | sed -n 's/.*"name":"\([^"]*\)".*"code":"\([^"]*\)".*/\1:\2/p' \
        | sort \
        | sed 's/\(.*\):\(.*\)/\2:\1/' \
        | column -t -s :
    exit
}

# Clean up before exit
trap cleanup SIGINT SIGTERM SIGHUP

# Check requirements
for command in sed egrep curl; do
    type $command &>/dev/null || error "This script requires $command"
done

# Check if sed is GNU or not
sed --version | egrep -q "GNU sed" || cat <<EOF

Warning:
This script is build for and tested only with GNU sed.
It looks like you maybe are using a different version of sed.
If thats not the case, just ignore this message :)

EOF

# Settings
RECURSIVE=1
CLEANUP=1
# Export language so all sub-shells have the same setting
export LANG_CODE

# URL to language list
lang_list_url="http://mediator.jw.org/v1/languages/E/web"

# Arguments
while [[ $1 ]]; do
    case $1 in
        --help) show_help
            ;;
        --no-recursive) RECURSIVE=0
            ;;
        --no-cleanup) CLEANUP=0
            ;;
        --lang)
            if lang_check "$2"; then
                LANG_CODE="$2"
                shift
            else
                lang_list
            fi
            ;;
        --*) error "Unknown flag: $1"
            ;;
        *) break
            ;;
    esac
    shift
done

# The default language to download
[[ -z $LANG_CODE ]] && LANG_CODE=E

dir_root="${1:-/tmp/kodiator/$LANG_CODE}"

url_root="http://mediator.jw.org/v1/categories/${LANG_CODE}/"
url_sub="${2:-VideoOnDemand}"
url_suffix="?detailed=1"

history_file="/tmp/.kodiator.history"
temp_file="/tmp/.kodiator.tmp"
array_root="kodiator_${url_sub}"


##### HEAD


# Do not process already processed files
[[ -e ${history_file} ]] && egrep -q "^${url_sub}$" "${history_file}" && exit
# Write to history file
echo "${url_sub}" >> "${history_file}"

echo "$url_sub: Processing"

# Download and process the file
# Note: Here, a pipe is used. Commands in a pipe is run in a sub-shell.
# Thus we can not keep the variables saved by these commands.
# So we dump the output to a file and let parse_lines() deal with creating
# the variables later.
(
    curl --silent "${url_root}${url_sub}${url_suffix}" || error "$url_sub: Download failed"
) | unsquash_file > "${temp_file}" || error

# Process and save all values in variables
parse_lines "${array_root}" < "${temp_file}" || error

[[ ${!array_root} ]] || error "$url_sub: Nothing to save"

# Read the variables and create directories containing STRM-files.
eval 'recursive_read \
    "${dir_root}" \
    ${array_root} \
    ${'"${array_root}"'[@]}\
    ' || error

cleanup

echo "$url_sub: Done"
