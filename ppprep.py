#!/usr/bin/env python

"""ppprep

Usage:
  ppprep [-abcip] <infile>
  ppprep [-abcip] <infile> <outfile>
  ppprep -h | --help
  ppprep -v | --version

Automates various tasks in the post-processing of books for pgdp.org using the ppgen post-processing tool.  Run ppprep as a first step on an unedited book text.

Examples:
  ppprep school.txt
  ppprep school-src.txt school2-src.txt

Options:
  -h --help             Show help.
  -v --version          Show version.
  -i --illustrations    Convert [Illustration] tags into ppgen .il/.ca markup 
  -p --pagenumbers      Convert page breaks into ppgen // 001.png style 
  -b --blankpages       Comment out [Blank Page] lines
  -c --headings         Convert chapter and section headings into ppgen style chapter and section headings
  -a --all              Perform all actions (default)
"""  

from docopt import docopt
from PIL import Image
import glob
import re
import os
import sys



# Create dictionary of illustrations in /image (id, file name, scan page number, width, caption)
	# assumes that images are named in the format i_<scan page number>.jpg
# For each [Illustration: caption] tag
  # parse caption 
  # comment out original [Illustration: caption] tag with .ig 
  
#TODO:
#multiline caption support

inBuf = []
outBuf = []
lineNum = 0
currentScanPage = 0
encoding = ""


# Replace : [Blank Page]
# with    : // [Blank Page]
def processBlankPages( inBuf ):
	outBuf = []
	lineNum = 0
	
	while lineNum < len(inBuf):
		m = re.match(r"^\[Blank Page]", inBuf[lineNum])
		if( m ):        
			outBuf.append("// [Blank Page]")
			lineNum += 1
		
		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;
	
# Replace : -----File: 001.png---\sparkleshine\swankypup\Kipling\SeaRose\Scholar\------
# with    : // 001.png
def processPageNumbers( inBuf ):
	outBuf = []
	lineNum = 0
	
	while lineNum < len(inBuf):
		m = re.match(r"^-----File: (\d\d\d\.png).*", inBuf[lineNum])
		if( m ):        
			outBuf.append("// " +  m.group(1))
			lineNum += 1
		
		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;
	
def isLineBlank( line ):
	return re.match( r"^\s*$", line )
	
def isLineComment( line ):
	print("***FOUND COMMENT: line")
	return re.match( r"^\/\/ *$", line )
	
def formatAsID( s ):
	s = re.sub(r" ", '_', s)        # Replace spaces with underscore    
	s = re.sub(r"[^\w\s]", '', s)   # Strip everything but alphanumeric and _
	s = s.lower()                   # Lowercase

	return s
	
def findPreviousNonEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum < len(buf) and isLineBlank(buf[lineNum]):
		lineNum -= 1
	
	return lineNum
	
def findNextNonEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum >= 0 and isLineBlank(buf[lineNum]):
		lineNum += 1
	
	return lineNum
	
def processHeadings( inBuf ):
	outBuf = []
	lineNum = 0 
	consecutiveEmptyLineCount = 0
	foundChapterHeadingStart = False

	while lineNum < len(inBuf):
#       print(lineNum)
		# Chapter heading blocks are in the form:
			# (4 empty lines)
			# chapter name
			# (1 empty line)
			# chapter description, opening quote, etc., 1 empty line seperating each
			# ...
			# (2 empty lines)
		
		# Chapter heading
		if( consecutiveEmptyLineCount == 4 and not isLineBlank(inBuf[lineNum]) ):
			inBlock = []
			outBlock = []
			foundChapterHeadingEnd = False;
			consecutiveEmptyLineCount = 0;
		
			# Copy chapter heading block to inBlock
			while( lineNum < len(inBuf) and not foundChapterHeadingEnd ):
				if( isLineBlank(inBuf[lineNum]) ):
					consecutiveEmptyLineCount += 1
					if( consecutiveEmptyLineCount == 2 ):
						foundChapterHeadingEnd = True
						consecutiveEmptyLineCount = 0
				else:
					consecutiveEmptyLineCount = 0
				
				if( foundChapterHeadingEnd ):
					# Remove trailing empty lines from chapter heading block
					inBlock = inBlock[:-1]
					# Rewind parser (to handle back to back chapter headings)
					lineNum = findPreviousNonEmptyLine(inBuf, lineNum) + 1
#                   lineNum -= 1
				else:
					inBlock.append(inBuf[lineNum])
					lineNum += 1
			
			# Title pages look like chapter headings but start with /*, handle it
			if( re.match(r"^\/\*$", inBlock[0]) ):
#               print("********* FALSE HIT, NOT A CHAPTER HEADING *********")
				for line in inBlock:
					outBlock.append(line)
			
			# Convert chapter heading to ppgen format
			else:
				# Remove three of the four consecutive blank lines from output buf
				outBuf = outBuf[:-4]
			
				# .sp 4
				# .h2 id=chapter_vi
				# CHAPTER VI.||chapter description etc..
				# .sp 2             
				chapterID = formatAsID(inBlock[0])
				chapterLine = ""
				for line in inBlock:
					chapterLine += line
					chapterLine += "|"
				chapterLine = chapterLine[:-1]
				
				outBlock.append("// ******** PPPREP GENERATED **************************************") 
				outBlock.append(".sp 4")
				outBlock.append(".h2 id=" + chapterID )             
				outBlock.append(chapterLine)
				outBlock.append(".sp 2")

				# Write out original as a comment
				outBlock.append(".ig  // *** PPPREP BEGIN ORIGINAL *********************************") 
				outBlock.append("") 
				outBlock.append("") 
				outBlock.append("") 
				outBlock.append("") 
				for line in inBlock:
					outBlock.append(line)
				outBlock.append(".ig- // *** END ***************************************************")
					
			# Write out chapter heading block
			for line in outBlock:
				outBuf.append(line)
				
		# Section heading
#       elif( consecutiveEmptyLineCount == 2 and not isLineBlank(inBuf[lineNum]) ):
#           print("*** FOUND SECTION HEADING ***")
#           print(outBuf[lineNum:-2])
#           print(outBuf[lineNum:-1])
#           print(outBuf[lineNum])
#           print("*****************************") 
			
		else:
			if( isLineBlank(inBuf[lineNum]) ):
				consecutiveEmptyLineCount += 1
			else:
				consecutiveEmptyLineCount = 0

			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;
	
def processIllustrations( inBuf ):
	# Build dictionary of images
#   files = [f for f in os.listdir('./images') if re.match(r'.*\.jpg', f)]
	files = glob.glob("images/*")
#   print(files)
	
	illustrations = {}

	# Build dictionary of illustrations in images folder
	for f in files:
		try:
			img = Image.open(f)
			img.load()
		except:
			print("Unable to load image", f)
			sys.exit(1)

#       print(f, img.size);     
		m = re.match(r"images/i_([^\.]+)", f)
		if( m ):        
			scanPageNum = m.group(1)
			anchorID = "i"+scanPageNum
#           print(anchorID)
			caption = "test"    
			f = re.sub(r"images/", "", f)
			illustrations[scanPageNum] = ({'anchorID':anchorID, 'fileName':f, 'scanPageNum':scanPageNum, 'dimensions':img.size, 'caption':caption })
#           print(illustrations);

	# Find and replace [Illustration: caption] markup
	outBuf = []
	lineNum = 0
	currentScanPage = 0
		
	while lineNum < len(inBuf):
#       print( str(lineNum) + " : " + inBuf[lineNum] )  
		
		# Keep track of active scanpage
		m = re.match(r"\/\/ (\d+)\.png", inBuf[lineNum])
		if( m ):
			currentScanPage = m.group(1)
#           print( currentScanPage)

		# Copy until next illustration block
		if( re.match(r"^\[Illustration", inBuf[lineNum]) ):
#           print("**************************************************\n")
#           print( inBuf[lineNum] ) 
			inBlock = []
			outBlock = []
		
			# Copy illustration block
			inBlock.append(inBuf[lineNum])
			while( lineNum < len(inBuf)-1 and not re.search(r"]$", inBuf[lineNum]) ):
#               print(str(lineNum))
#               print(str(len(inBuf)))
#               print( inBuf[lineNum] ) 
				lineNum += 1
				inBlock.append(inBuf[lineNum])
			

#           print( inBlock )    
#           print("**************************************************\n")
			lineNum += 1
			
			# Convert to ppgen illustration block
#           .il id=i_001 fn=i_001.jpg w=600 alt=''
#           .ca SOUTHAMPTON BAR IN THE OLDEN TIME.
			outBlock.append( ".il id=i" + currentScanPage + " fn=" +  illustrations[currentScanPage]['fileName'] + " w=" + str(illustrations[currentScanPage]['dimensions'][0]) + " alt=''" )
			captionLine = ""
			for line in inBlock:
				line = re.sub(r"^\[Illustration: ", "", line)
				line = re.sub(r"^\[Illustration", "", line)
				line = re.sub(r"]$", "", line)
				captionLine += line
				captionLine += "<br/>"

#           captionLine = captionLine[:-(len("<br/>")]
			
			outBlock.append( ".ca " + captionLine );
			
#           print( outBlock)
			
			# Write out ppgen illustration block
			for line in outBlock:
				outBuf.append(line)
				
			# Write out boilerplate code for HTML version as comment in case .il is not sufficient
			outBuf.append(".ig  // *** PPPREP BEGIN ************************************************************")
			outBuf.append("// ******** Alternative inline HTML version for use when .il .ca are insufficient ***") 
			outBuf.append(".if h")
			outBuf.append(".de .customCSS { clear:left; float:left; margin:4% 4% 4% 0; }")
			outBuf.append(".li")
			outBuf.append("<div class='customCSS'>")
			outBuf.append("<img src='" + illustrations[currentScanPage]['fileName'] + "' alt='' />")
			outBuf.append("</div>")
			outBuf.append(".li-")
			outBuf.append(".if-")
			outBuf.append(".if t")
			for line in inBlock:
				outBuf.append(line)
			outBuf.append(".if-")           
			outBuf.append(".ig- // *** END *********************************************************************")
			
		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1
	
	return outBuf;
			
def loadFile(fn):
	inBuf = []
	encoding = ""
	
	if not os.path.isfile(fn):
		fatal("specified file {} not found".format(fn))

	if encoding == "":
		try:
			wbuf = open(fn, "r", encoding='ascii').read()
			encoding = "ASCII" # we consider ASCII as a subset of Latin-1 for DP purposes
			inBuf = wbuf.split("\n")
		except Exception as e:
			pass

	if encoding == "":
		try:
			wbuf = open(fn, "rU", encoding='UTF-8').read()
			encoding = "utf_8"
			inBuf = wbuf.split("\n")
			# remove BOM on first line if present
			t = ":".join("{0:x}".format(ord(c)) for c in inBuf[0])
			if t[0:4] == 'feff':
				inBuf[0] = inBuf[0][1:]
		except:
			pass

	if encoding == "":
		try:
			wbuf = open(fn, "r", encoding='latin_1').read()
			encoding = "latin_1"
			inBuf = wbuf.split("\n")
		except Exception as e:
			pass

	if encoding == "":
		self.fatal("cannot determine input file decoding")
	else:
		# self.info("input file is: {}".format(encoding))
		if encoding == "ASCII":
			encoding = "latin_1" # handle ASCII as Latin-1 for DP purposes

	for i in range(len(inBuf)):
		inBuf[i] = inBuf[i].rstrip()

	return inBuf;
	
# display error message and exit
def fatal(message):
	sys.stderr.write("FATAL: " + message + "\n")
	exit(1)

# display warning
def warn(message):
	if message not in self.warnings: # don't give exact same warning more than once.
		self.warnings.append(message)
		sys.stderr.write("**warning: " + message + "\n")


def main():
	try:
		args = arguments = docopt(__doc__, version='ppprep 0.1')
		print(args)

		# Process required command line arguments
		outfile = "out.txt"
		if( args['<outfile>'] ):
			outfile = args['<outfile>']
			
		infile = args['<infile>']

		# Open source file and represent as an array of lines
		inBuf = loadFile( infile )

		# Process optional command line arguments
		doPageNumbers = args['--pagenumbers'];
		doBlankPages = args['--blankpages'];
		doIllustrations = args['--illustrations'];
		doHeadings = args['--headings'];
		
		# Default to --all if no other options set
		if( not doPageNumbers and \
			not doBlankPages and \
			not doIllustrations and \
			not doHeadings or \
			args['--all'] ):
			doPageNumbers = True;
			doBlankPages = True;
			doIllustrations = True;
			doHeadings = True;
				
		# Process source document
		outBuf = []
		if( doHeadings ):
			outBuf = processHeadings( inBuf )
			inBuf = outBuf
		if( doBlankPages ):
			outBuf = processBlankPages( inBuf )
			inBuf = outBuf
		if( doPageNumbers or doIllustrations ):
			outBuf = processPageNumbers( inBuf )
			inBuf = outBuf
		if( doIllustrations ):
			outBuf = processIllustrations( inBuf )
			inBuf = outBuf

		# Save file
		f = open(outfile,'w')
		for line in outBuf:
			f.write(line+'\n')
		f.close()
		
	except docopt.DocoptExit as e:
		print(e.message)
		
		return


if __name__ == "__main__":
	main()
