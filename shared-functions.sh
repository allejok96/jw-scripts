#!/bin/bash
#
# functions for jw-scripts
#

error()
{
    echo "${@:-Something went wrong}" 1>&2
    exit 1
}

# Remove everything but the videos
clean_dir()
{
    # Remove links
    find "$datadir" -type l -delete
    # Remove playlists
    find "$datadir" -name "*.m3u" -delete
    # Remove empty directories
    find "$datadir" -type d -exec rmdir --ignore-fail-on-non-empty {} +
}

# Make a link (but smarter)
# Args: DEST LINKNAME
create_link()
{
    [[ $1 && $2 ]] || error "Error in create_link()"

    # Does link exist?
    if [[ -L "$2" ]]; then
	# Is link destination same as we want?
	if [[ $(readlink "$2") = "$1" ]]; then
	    return 0
	else
	    # If not, remove it
	    rm "$2" || error "$2: Failed to remove link"
	fi
    fi

    # Make the actual link
    # -r makes it relative
    ln -sr "$1" "$2" || error "$2: Failed to create link"
}

# Add newline around squiggly and square brackets and commas
# but not if they are quoted
# Keep only the lines starting with "KEYWORD":
# and remove all unescaped citation marks
# Args: [KEYWORD ...]
unsquash_file()
{
    if [[ $@ ]]; then
        # Append \| to all parameters
        # and remove the last one
        keywordstring="$(printf '%s\|' "$@" | sed 's/\\|$//')"
    else
        # Match everything that's not a citation mark
        keywordstring='[^"]*'
    fi

    sed '
        # Add a newline after all "special" characters
        # Note how the character list starts with an ]
        # Smart huh?
        s/[][{},]/\n&\n/g

' | sed -n '
        : start
        # Does this row have an uneven number of citation marks?
        # That means that the quote continues on the next line...
        /^\([^"\n]*"[^"\n]*"\)*[^"\n]*"[^"\n]*$/ {
            # Append the next line of input
            N
            # Remove the newline between the two lines of input
            s/\n//g
            # Go back to start again
            b start
        }
        # If the line is fine...
        # Grep only the keywords
        /^"\('"$keywordstring"'\)":/ {
            # Remove all unescaped citation marks
            s/\(^\|[^\]\)"/\1/g
            # And print it
            p
        }
' || error "Failed to format JSON"
}

# Create empty dir and playlist
# Args: DATADIR CODE
initialize_dir()
{
    local datadir="$1"
    local code="$2"

    [[ $datadir && $code ]] || error "Error in initialize_dir()"

    ((filesystem)) && datadir="$datadir/$code"
    
    # Create directory
    if [[ ! -d $datadir ]]; then
        mkdir -p "$datadir" || error "$datadir: Failed to create directory"
    fi

    ! ((filesystem)) && reset_playlist "$datadir/$code.m3u"
    
    return 0
}

# Create a link to the CODE outside DATADIR for easy access
# Args: CODE NAME DATADIR
create_index_file_link()
{
    local code="$1"
    local name="$2"
    local datadir="$3"
    
    if ((filesystem)); then
        create_link "$datadir/$code" "$datadir/../$name"
    else
        create_link "$datadir/$code.m3u" "$datadir/../$name.m3u"
    fi
}

# Save link to other playlist/dir
# in current playlist/dir
# Args: NAME DESTCODE DATADIR CODE
write_subdir()
{
    local title="$1"
    local link="$2"
    local datadir="$3"
    local code="$4"
        
    [[ $title && $link && $datadir && $code ]] || error "Error in write_subdir()"

    if ((filesystem)); then
	# Create a directory to link to first
	if [[ ! -d $datadir/$link ]]; then
	    mkdir -p "$datadir/$link" || error "$datadir/$link: Failed to create directory"
	fi
        create_link "$datadir/$link/" "$datadir/$code/$title"
    else
	write_to_playlist "$title" "$link.m3u" "$datadir/$code.m3u"
    fi

    return 0
}

# Save videos in playlist/dir
# and optionally download them
# Args: TITLE LINK DATADIR CODE
write_media()
{
    local title="$1"
    local link="$2"
    local file="$(basename "$link")"
    local datadir="$3"
    local code="$4"

    [[ $title && $link && $file && $datadir && $code ]] || error

    # Download video
    if ((download)); then
        if [[ ! -e $datadir/$file ]]; then
            echo "Downloading: $file" 1>&2
            download_file "$link" > "$datadir/$file"
        fi
        # Change link to point to the local video
        link="$file"
    fi

    if ((filesystem)) && ((download)); then
	# Get the file name extension
	suffix="$(sed -n 's/.\+\.//p' <<< "$file")"
        # Link to a existing media
        create_link "$datadir/$file" "$datadir/$code/$title.$suffix"
    elif ((filesystem)); then
        # Create a playlist with a video URL and link to it
	reset_playlist  "$datadir/$file.m3u"
	write_to_playlist "$title" "$link" "$datadir/$file.m3u"
        create_link "$datadir/$file.m3u" "$datadir/$code/$title.m3u"
    else
        # Add the video URL to a playlist
        write_to_playlist "$title" "$link" "$datadir/$code.m3u"
    fi

    return 0
}

reset_playlist()
{
    printf '%s\n' "#EXTM3U" > "$1"
}

# Args: [-r] NAME LINK FILE
write_to_playlist()
{
    local title="$1"
    local link="$2"
    local file="$3"
    [[ $title && $link && $file ]] || error "Error in write_to_playlist()"

    # Reset the file
    if [[ ! -e $file ]]; then
	reset_playlist "$file"
    fi

    # If we are the first process, and the link is local a file
    # add the subdir to the link (since first process saves
    # outside the subdir)
    if ! ((child)) && [[ ! $link =~ ^https?:// ]]; then
	local subdir="$(basename "$(realpath -m "$datadir")")"
	[[ $subdir ]] || error "Error in write_to_playlist()"
	link="$subdir/$link"
    fi
    
    printf '%s\n' "#EXTINF:0,$title" "$link" >> "$file" || error "$file: Failed to write to playlist"
}

# Download a file with curl or wget
# Args: URL [RATE]
download_file()
{
    [[ $1 ]] || error "Error in download_file()"

    echo "$1" 1>&2
    
    if ((hascurl)); then
        curl ${maxrate:+--limit-rate "$maxrate"} --silent "$1" || error "Failed to download file"
    else
        wget ${maxrate:+--limit-rate "$maxrate"} --quiet -O - "$1" || error "Failed to download file"
    fi
}

# Check that we have all we need
requirement_check()
{
    type sed &>/dev/null || error "This script requires GNU sed"

    if type curl &>/dev/null; then
        export hascurl=1
    else
        type wget &>/dev/null || error "This script requires curl or wget"
        export hascurl=0
    fi

    sed --version | egrep -q "GNU sed" || cat <<EOF
Warning:
This script is build for and tested only with GNU sed.
It looks like you are using a different version of sed,
so I canot guarrantee that it will work for you.
Just saying :)

EOF

    return 1
}

# Read the arguments and save variables or do things
# Args: --flag=variable --flag:action -- arguments ...
read_arguments()
{
    until [[ $1 = -- ]]; do
        flags+=("$1")
        shift
        [[ $# = 0 ]] && error "Error in read_arguments()"
    done

    # Remove the --
    shift

    until [[ $# = 0 ]]; do
        for flag in "${flags[@]}"; do

            # Normal flag
            if [[ $flag =~ --[a-zA-Z0-9-]+:.* && $1 = "${flag%%:*}" ]]; then
                # Run action
                eval "${flag#*:}"
                shift
                continue 2

            # Flag with argument, separated by =
            elif [[ $flag =~ --[a-zA-Z0-9-]+=.* && $1 = "${flag%%=*}"=* ]]; then
                # Check that we have the argument
                [[ ${1#*=} ]] || error "${flag%%=*} requires an argument"
                # Save in variable
                eval "${flag#*=}"'="${1#*=}"'
                shift
                continue 2

            # Flag with argument, separated by space (and argument is not a flag)
            elif [[ $flag =~ --[a-zA-Z0-9-]+=.* && $1 = "${flag%%=*}" && $2 != --* ]]; then
                # Check that we have the argument
                [[ $2 ]] || error "${flag%%=*} requires an argument"
                # Save in variable
                eval "${flag#*=}"'="$2"'
                shift 2
                continue 2

            # An argument, save in array
            elif [[ $1 != --* ]]; then
                arguments+=("$1")
                shift
                continue 2
            fi

        done

        # No matching flag
        error "$1: unknown flag"

    done

    return 0
}

# Check that the language code is valid
# Args: LANGCODE URL PATTERN
check_lang()
{
    [[ $1 && $2 && $3 ]] || error "Error in check_lang()"

    [[ $1 = E || $NOCHECKLANG = 1 ]] && return 0
    # Don't make more checks
    export NOCHECKLANG=1
    # Try to find the language code in the text
    # End with that exit code
    download_file "$2" | grep -q "$3"

    return $?
}
