#!/bin/bash
#
# kodiator
#
# Requires: GNU sed, curl/wget
#
# Index tv.jw.org by processing the files from mediator.jw.org
# and create m3u playlists, which can be played by e.g. Kodi.
# Thereby the name Kodiator.
#

cleanup()
{
    [[ -e /tmp/.kodiator.history ]] && rm "${history_file}"
}

error()
{
    echo "${@:-Something went wrong}" 1>&2
    exit 1
}

show_help()
{
    cat<<EOF
Index tv.jw.org and save the video links in m3u playlists

Usage: kodiator [options] [DIRECTORY]
  --lang LANGUAGE       Language to download. Selecting no language
                        will show a list of available language codes
  --no-recursive        Just download this file/category
  --category CATEGORY   Name of the file/category to index
  DIRECTORY             Directory to save the playlists in

  
EOF
    exit
}

# Add newline around squiggly and square brackets and replace commas with newline
# but do nothing if they are quoted
unsquash_file()
{
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
	# If the line is fine, print it
	p
' | sed '
	# Remove all commas and empty lines
	/^,\?$/d
'
}

# Read the formated json file on stdin
# write videos to playlists
# create new playlists for each category
# and download and parse the json files for that category
parse_lines()
{    
    # Read stdin
    while read -r; do
	case "$REPLY" in
	    # Move down to a new sublevel
	    \{|\[)
		# If the current level has name and key = new sub-playlist
		if [[ ${name[$level]} && ${key[$level]} ]]; then
		    # Process the file for $key
		    ((RECURSIVE)) && "$0" --category "${key[$level]}"
		    # Print the name of the new playlist to the current one
		    print_to_file "# ${name[$level]}"
		    print_to_file "${key[$level]}.m3u"
		    filename+=([$level]="${key[$level]}")
		fi
		# Change level
		level+=1
		;;
	    # Move one level up
	    \}|\])
		# If the current level has title and url = video
		if [[ ${title[$level]} && ${url[$level]} ]]; then
		    # Print to the playlist
		    print_to_file "# ${title[$level]}"
		    print_to_file "${url[$level]}"
		fi
		# Unset all the variables for this level
		unset title[$level] name[$level] key[$level] url[$level] filename[$level]
		# Change level
		level+=-1
		;;
	    "title":*)
		title+=([$level]="$REPLY")
		;;
	    "name":*)
		name+=([$level]="$REPLY")
		;;
	    "key":*)
		key+=([$level]="$REPLY")
		;;
	    "progressiveDownloadURL":*)
		url+=([$level]="$REPLY")
		;;
	esac
    done
}

# Print text to the playlist file that's set
# in the array $filename
print_to_file()
{
    # The current filename is the last one in the array
    local file="$savedir/${filename[-1]}.m3u"
    # Create directory
    if [[ ! -e $savedir ]]; then
	mkdir -p "$savedir" || error "$savedir: Failed to create directory"
    fi
    # Add header to file if it doesn't exist
    [[ ! -e $file ]] && echo "#EXTM3U" > "$file"
    printf '%s\n' "$*" >> "$file"
}

# Download the language list and make it readable
# Note: This is probably not very failsafe
lang_list()
{
    # 1. Download the list
    # 2. Make newline at every opening bracket
    #    where a new language starts
    # 3. Replace "name":"LANG" ... "code":"CODE"
    #    with LANG CODE
    # 4. Sort it
    # 5. Switch place on LANG and CODE
    # 6. Make a nice list with columns
    curl --silent "$1" \
        | sed 's/{/\n/g' \
        | sed -n 's/.*"name":"\([^"]*\)".*"code":"\([^"]*\)".*/\1:\2/p' \
        | sort \
        | sed 's/\(.*\):\(.*\)/\2:\1/' \
        | column -t -s :
}

# Clean up before exit
trap 'cleanup' SIGINT SIGTERM SIGHUP

# Check requirements
type sed &>/dev/null || error "This script requires GNU sed"
if type curl &>/dev/null; then
    CURL=1
else
    type wget &>/dev/null || error "This script requires curl or wget"
    CURL=0
fi
sed --version | egrep -q "GNU sed" || cat <<EOF
Warning:
This script is build for and tested only with GNU sed.
It looks like you are using a different version of sed,
so I can't guarrantee that it will work for you.
Just saying :)

EOF

export lang savedir
lang=E
RECURSIVE=1
category=VideoOnDemand

# Arguments
while [[ $1 ]]; do
    case $1 in
        --help) show_help
            ;;
        --no-recursive) RECURSIVE=0
            ;;
        --lang)
	    langurl="http://mediator.jw.org/v1/languages/E/web"
            if curl --silent "$langurl" | grep -q "\"code\":\"$2\""; then
                lang="$2"
                shift
            else
                lang_list "$langurl"
		exit
            fi
            ;;
	--category)
	    category="$2"
	    shift
	    ;;
        --*) error "Unknown flag: $1"
            ;;
        *) break
            ;;
    esac
    shift
done

savedir="${1:-./kodiator/$lang}"

# Check the history if we processed this already
histfile="/tmp/.kodiator.history"
[[ -e $histfile ]] && grep "^${category}$" "$histfile" && exit
echo "$category" | tee -a "$histfile"

# Download and parse the json file
baseurl="http://mediator.jw.org/v1/categories/$lang/${category}?detailed=1"
if ((CURL)); then
    curl --silent "$baseurl" || error "Failed to download file"
else
    wget --quiet -O - "$baseurl" || error "Failed to download file"
fi | unsquash_file | parse_lines || error

