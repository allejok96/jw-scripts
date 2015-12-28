#!/bin/bash
#
# functions for jw-scripts
#

error()
{
    echo "${@:-Something went wrong}" 1>&2
    exit 1
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
' || error
}

# Print text to the playlist
# Args: TITLE LINK FILENAME
print_to_file()
{
    [[ $# != 3 ]] && error
    
    # Write to file
    printf '%s\n' "#EXTINF:0,$1" "$2" >> "$3" || error "Failed to write to playlist"
}

# Download a file with curl or wget
# Args: URL
download_file()
{
    [[ $# != 1 ]] && error

    if ((CURL)); then
	curl --silent "$1" || error "Failed to download file"
    else
	wget --quiet -O - "$1" || error "Failed to download file"
    fi
}

# Check that we have all we need
requirement_check()
{
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
}

# Read the arguments and save variables or do things
# Args: --flag=variable --flag:action -- arguments ...
read_arguments()
{
    until [[ $1 = -- ]]; do
	flags+=("$1")
	shift
	[[ $# = 0 ]] && error
    done

    # Remove the --
    shift
    
    until [[ $# = 0 ]]; do
	for flag in "${flags[@]}"; do

	    # Normal flag
	    if [[ $flag =~ --[a-zA-Z0-9]+:.* && $1 = "${flag%%:*}" ]]; then
		# Run action
		eval "${flag#*:}"
		shift
		continue 2

	    # Flag with argument, separated by =
	    elif [[ $flag =~ --[a-zA-Z0-9]+=.* && $1 = "${flag%%=*}"=* ]]; then
		# Check that we have the argument
		[[ ${1#*=} ]] || error "${flag%%=*} requires an argument"
		# Save in variable
		eval "${flag#*=}"'="${1#*=}"'
		shift
		continue 2

	    # Flag with argument, separated by space (and argument is not a flag)
	    elif [[ $flag =~ --[a-zA-Z0-9]+=.* && $1 = "${flag%%=*}" && $2 != --* ]]; then
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
}

# Check that the language code is valid
# Args: LANGCODE URL PATTERN
check_lang()
{
    [[ $# != 3 ]] && error

    [[ $1 = E || $NOCHECKLANG = 1 ]] && return 0
    # Don't make more checks
    export NOCHECKLANG=1
    # Try to find the language code in the text
    download_file "$2" | grep -q "$3" # no error here, we end with exit code
}
