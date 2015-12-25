#!/bin/bash
#
# bible-index
#
# Requires: GNU sed, curl/wget
#

error()
{
    echo "${@:-Something went wrong}" 1>&2
    exit 1
}

show_help()
{
    cat<<EOF
Index the bible recordings from jw.org and make m3u playlists

Usage: kodiator [options] [DIRECTORY]
  --lang LANGUAGE       Language to download. Selecting no language
                        will show a list of available language codes
  --book BOOK           Number of the bible book to index
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
# write mp3 files to playlists
# and download and parse new books
#
# GIGANT CAVEATS:
# - "pubName" must be first, because it erases the playlist
# - "title" must be followed by "booknum" or by "stream"
# - "pubName" must be the same as the parent books "title"
#     or else the link to the file and the actual file
#     will be different.
#
parse_lines()
{
    # Create directory
    if [[ ! -e $savedir ]]; then
	mkdir -p "$savedir" || error "$savedir: Failed to create directory"
    fi
    
    # Read stdin
    # Use -r because we want to keep the backslashes a bit longer
    while read -r; do
	# Remove quotes
	input="${REPLY//\"/}"
	# Unescape
	input="$(printf '%b' "$input")"
	# Remove backslashes
	input="${input//\\/}"

	case "$input" in
	    pubName:*)
		name="${input#*:}"
		# Message, so we can see progress
		echo "$name" 1>&2
		# Start on an empty playlist
		echo "#EXTM3U" > "$savedir/$book - $name.m3u"
		;;
	    title:*)
		title="${input#*:}"
		;;
	    booknum:*)
		num="${input#*:}"
		# Only create links to books if our book is the "index"
		# and the link don't point to the index itself.
		if [[ $book = 0 && $num != 0 ]]; then
		    print_to_file "# $title" "$num - $title.m3u"
		    ("$0" --book "$num")
		fi
		;;
	    stream:*.mp3)
		url="${input#*:}"
		print_to_file "# $title" "$url"
		;;
	esac
    done
}

# Print text to the playlist
print_to_file()
{
    # Write to file
    printf '%s\n' "$@" >> "$savedir/$book - $name.m3u"
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
    download_file "$langurl" \
        | sed 's/{/\n/g' \
        | sed -n 's/.*"name":"\([^"]*\)".*"code":"\([^"]*\)".*/\1:\2/p' \
        | sort \
        | sed 's/\(.*\):\(.*\)/\2:\1/' \
        | column -t -s :
}

# Download a file with curl or wget
download_file()
{
    if ((CURL)); then
	curl --silent "$1" || error "Failed to download file"
    else
	wget --quiet -O - "$1" || error "Failed to download file"
    fi
}

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
so I canot guarrantee that it will work for you.
Just saying :)

EOF

# Arguments
while [[ $1 ]]; do
    case $1 in
        --help) show_help
            ;;
        --lang)
	    if [[ $2 ]]; then
		lang=$2
	    else
		LANGLIST=1
	    fi
            ;;
	--book)
	    book="$2"
	    shift
	    ;;
        --*) error "Unknown flag: $1"
            ;;
        *) break
            ;;
    esac
    shift
done

export lang savedir
savedir="${1:-./Bible-$lang}"
[[ $lang ]] || lang=E
[[ $book ]] || book=0
langurl="http://mediator.jw.org/v1/languages/E/web"
baseurl="http://www.jw.org/apps/TRGCHlZRQVNYVrXF?booknum=$book&output=json&pub=bi12&fileformat=MP3&alllangs=0&langwritten=$lang&txtCMSLang=$lang"

# Check if language is correct
download_file "$langurl" | grep -q "\"code\":\"$lang\"" || LANGLIST=1

# Show the language list, maybe
if ((LANGLIST)); then
    lang_list
    exit
fi

# Download and parse the JSON file
download_file "$baseurl" | unsquash_file | parse_lines || error

