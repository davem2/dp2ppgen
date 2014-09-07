#!/usr/bin/env python

from docopt import docopt
from PIL import Image



# Create dictionary of illustrations in /image (id, file name, scan page number, width, caption)
	# assumes that images are named in the format i_<scan page number>.jpg
# For each [Illustration: caption] tag
  # parse caption 
  # comment out original [Illustration: caption] tag with .ig 
  
#TODO:
#multiline caption support

"""ppimg

Usage:
  ppimg <infile> <outfile>

ppimg automates the process of replacing [Illustration] tags with the appropriate ppgen markup

Examples:
  ppimg school-src.txt school2-src.txt

Options:
  -t --tbd  CHANGEME
  
"""  

def processIllustrations( infile, outfile ):
	# Build dictionary of images
	files = [f for f in os.listdir('./images') if re.match(r'i_[0-9][0-9][0-9].*\.jpg', f)]
	
	return

def main():
	args = arguments = docopt(__doc__, version='ppimg 0.1')
	print(args)

	# Process source document
	processIllustrations( args['infile'],  args['outfile'] )
		
	return


if __name__ == "__main__":
    main()
