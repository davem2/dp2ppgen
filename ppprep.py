#!/usr/bin/env python

"""ppprep

Usage:
  ppprep [-cdefkpqv] <infile>
  ppprep [-cdefkpqv] [--setfndest=<fndest>] <infile> <outfile>
  ppprep -h | --help
  ppprep ---version

Automates various tasks in the post-processing of books for pgdp.org using the ppgen post-processing tool.  Run ppprep as a first step on an unedited book text.

Examples:
  ppprep book.txt
  ppprep book-src.txt book2-src.txt

Options:
  -c, --chapters       Convert chapter headings into ppgen style chapter headings.
  -d, --dryrun         Run through conversions but do not write out result.
  -e, --sections       Convert section headings into ppgen style section headings.
  -f, --footnotes      Convert footnotes into ppgen format.
  --setfndest=<fndest> Where to relocate footnotes (paragraphend, chapterend, bookend)
  -k, --keeporiginal   On any conversion keep original text as a comment.
  -p, --pages          Convert page breaks into ppgen // 001.png style, add .pn statements and comment out [Blank Page] lines.
  -q, --quiet          Print less text.
  -v, --verbose        Print more text.
  -h, --help           Show help.
  --version            Show version.
"""

from docopt import docopt
import glob
import re
import os
import sys
import logging


# Removes trailing spaces and tabs from an array of strings
def removeTrailingSpaces( inBuf ):
	outBuf = []

	for line in inBuf:
		outBuf.append(line.rstrip(" \t"))

	return outBuf


# Replace : [Blank Page]
# with    : // [Blank Page]
def processBlankPages( inBuf, keepOriginal ):
	outBuf = []
	lineNum = 0

	logging.info("--- Processing blank pages")

	while lineNum < len(inBuf):
		m = re.match(r"^\[Blank Page]", inBuf[lineNum])
		if( m ):
			if( keepOriginal ):
				outBuf.append("// *** PPPREP ORIGINAL: " + inBuf[lineNum])
			outBuf.append("// [Blank Page]")
			logging.debug("Line " + str(lineNum) + ": convert " + inBuf[lineNum] + " ==> " + outBuf[-1])
			lineNum += 1

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;


# Replace : -----File: 001.png---\sparkleshine\swankypup\Kipling\SeaRose\Scholar\------
# with    : // 001.png
def processPageNumbers( inBuf, keepOriginal ):
	outBuf = []
	lineNum = 0

	logging.info("--- Processing page numbers")

	while lineNum < len(inBuf):
		m = re.match(r"^-----File: (\d\d\d\.png).*", inBuf[lineNum])
		if( m ):
			if( keepOriginal ):
				outBuf.append("// *** PPPREP ORIGINAL: " + inBuf[lineNum])
			outBuf.append("// " +  m.group(1))
			outBuf.append(".pn +1")
			logging.debug("Line " + str(lineNum) + ": convert " + inBuf[lineNum] + " ==> " + outBuf[-1])
			lineNum += 1

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;


def isLineBlank( line ):
	return re.match( r"^\s*$", line )


def isLineComment( line ):
	return re.match( r"^\/\/ *$", line )


def formatAsID( s ):
	s = re.sub(r" ", '_', s)        # Replace spaces with underscore
	s = re.sub(r"[^\w\s]", '', s)   # Strip everything but alphanumeric and _
	s = s.lower()                   # Lowercase

	return s


def findNextEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum < len(buf)-1 and not isLineBlank(buf[lineNum]):
		lineNum += 1
#		print("findNextEmptyLine({})".format(lineNum))
	return lineNum


def findPreviousEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum >= 0 and not isLineBlank(buf[lineNum]):
		lineNum -= 1
#		print("findPreviousEmptyLine({})".format(lineNum))
	return lineNum


def findNextNonEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum < len(buf)-1 and isLineBlank(buf[lineNum]):
		lineNum += 1
#		print("findNextNonEmptyLine({})".format(lineNum))
	return lineNum


def findPreviousNonEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum >= 0 and isLineBlank(buf[lineNum]):
		lineNum -= 1
#		print("findPreviousNonEmptyLine({})".format(lineNum))
	return lineNum


# find previous line that contains original book text (ignore ppgen markup, proofing markup, blank lines)
def findPreviousLineOfText( buf, startLine ):
	lineNum = findPreviousNonEmptyLine( buf, startLine )
	while( lineNum > 0 and re.match(r"[\.\*\#\/\[]", buf[lineNum]) ):
		lineNum = findPreviousNonEmptyLine( buf, lineNum-1 )
#		print("findPreviousLineOfText({})".format(lineNum))
	return lineNum


# find next line that contains original book text (ignore ppgen markup, proofing markup, blank lines)
def findNextLineOfText( buf, startLine ):
	lineNum = findNextNonEmptyLine( buf, startLine )
	while( lineNum < len(buf)-1 and re.match(r"[\.\*\#\/\[]", buf[lineNum]) ):
		lineNum = findNextNonEmptyLine( buf, lineNum+1 )
#		print("findNextLineOfText({})".format(lineNum))
	return lineNum


def findNextChapter( buf, startLine ):
	lineNum = startLine
	while( lineNum < len(buf)-1 and not re.match(r"\.h2", buf[lineNum]) ):
		lineNum += 1
	return lineNum
		

def processHeadings( inBuf, doChapterHeadings, doSectionHeadings, keepOriginal ):
	outBuf = []
	lineNum = 0
	consecutiveEmptyLineCount = 0
	rewrapLevel = 0
	foundChapterHeadingStart = False

	if( doChapterHeadings and doSectionHeadings ):
		logging.info("--- Processing chapter and section headings")
	if( doChapterHeadings ):
		logging.info("--- Processing chapter headings")
	if( doSectionHeadings ):
		logging.info("--- Processing section headings")

	while lineNum < len(inBuf):
		# Chapter heading blocks are in the form:
			# (4 empty lines)
			# chapter name
			# can span more than one line
			# (1 empty line)
			# chapter description, opening quote, etc., 1 empty line seperating each
			# ...
			# (2 empty lines)

		# Section heading blocks are in the form
			# (2 empty lines)
			# section name
			# can span more than one line
			# (1 empty line)

		# Out-of-line formatting /# #/ /* */
		if( re.match(r"^\/\*$", inBuf[lineNum]) or re.match(r"^\/\#$", inBuf[lineNum]) ):
			rewrapLevel += 1
		elif( re.match(r"^\*\/$", inBuf[lineNum]) or re.match(r"^\#\/$", inBuf[lineNum]) ):
			rewrapLevel -= 1

		# Chapter heading
		if( doChapterHeadings and consecutiveEmptyLineCount == 4 and not isLineBlank(inBuf[lineNum]) and rewrapLevel == 0 ):
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
				else:
					inBlock.append(inBuf[lineNum])
					lineNum += 1

			# Remove the four consecutive blank lines that preceeds chapter heading
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

			logging.debug("Found chapter heading: " + chapterLine)

			outBlock.append("// ******** PPPREP GENERATED ****************************************")
			outBlock.append(".sp 4")
			outBlock.append(".h2 id=" + chapterID )
			outBlock.append(chapterLine)
			outBlock.append(".sp 2")

			if( keepOriginal ):
				# Write out original as a comment
				outBlock.append(".ig  // *** PPPREP BEGIN ORIGINAL ***********************************")
				outBlock.append("")
				outBlock.append("")
				outBlock.append("")
				outBlock.append("")
				for line in inBlock:
					outBlock.append(line)
				outBlock.append(".ig- // *** END *****************************************************")

			# Write out chapter heading block
			for line in outBlock:
				outBuf.append(line)

			# Log action
			logging.info("------ .h2 " + chapterLine)

		# Section heading
		elif( doSectionHeadings and consecutiveEmptyLineCount == 2 and not isLineBlank(inBuf[lineNum]) and rewrapLevel == 0 ):
			inBlock = []
			outBlock = []
			foundSectionHeadingEnd = False;
			consecutiveEmptyLineCount = 0;

			# Copy section heading block to inBlock
			while( lineNum < len(inBuf) and not foundSectionHeadingEnd ):
				if( isLineBlank(inBuf[lineNum]) ):
					foundSectionHeadingEnd = True
				else:
					inBlock.append(inBuf[lineNum])
					lineNum += 1

			# Remove two consecutive blank lines that preceed section heading
			outBuf = outBuf[:-2]

			# .sp 2
			# .h3 id=section_i
			# Section I.
			# .sp 1
			sectionID = formatAsID(inBlock[0])
			sectionLine = ""
			for line in inBlock:
				sectionLine += line
				sectionLine += "|"
			sectionLine = sectionLine[:-1]

			logging.debug("Found section heading: " + sectionLine)

			outBlock.append("// ******** PPPREP GENERATED ****************************************")
			outBlock.append(".sp 2")
			outBlock.append(".h3 id=" + sectionID )
			outBlock.append(sectionLine)
			outBlock.append(".sp 1")

			if( keepOriginal ):
				# Write out original as a comment
				outBlock.append(".ig  // *** PPPREP BEGIN ORIGINAL ***********************************")
				outBlock.append("")
				outBlock.append("")
				for line in inBlock:
					outBlock.append(line)
				outBlock.append(".ig- // *** END *****************************************************")

			# Write out chapter heading block
			for line in outBlock:
				outBuf.append(line)

			# Log action
			logging.info("------ .h3 " + sectionID)
		else:
			if( isLineBlank(inBuf[lineNum]) ):
				consecutiveEmptyLineCount += 1
			else:
				consecutiveEmptyLineCount = 0

			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;


def loadFile(fn):
	inBuf = []
	encoding = ""

	if not os.path.isfile(fn):
		logging.critical("specified file {} not found" + format(fn))

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
		fatal("Cannot determine input file decoding")
	else:
		# self.info("input file is: {}".format(encoding))
		if encoding == "ASCII":
			encoding = "latin_1" # handle ASCII as Latin-1 for DP purposes

	for i in range(len(inBuf)):
		inBuf[i] = inBuf[i].rstrip()

	return inBuf;


def createOutputFileName( infile ):
	# TODO make this smart.. is infile raw or ppgen source? maybe two functions needed
	outfile = infile.split('.')[0] + "-out.txt"
	return outfile

def stripFootnoteMarkup( inBuf ):
	outBuf = []
	lineNum = 0
	
	while lineNum < len(inBuf):
		# copy inBuf to outBuf throwing away all footnote markup [Footnote...]
		if( re.match(r"[\*]*\[Footnote", inBuf[lineNum]) ):
			while( lineNum < len(inBuf) and not re.search(r"][\*]*$", inBuf[lineNum]) ):
				lineNum += 1			
			lineNum += 1
		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1
	
	return outBuf

def parseFootnotes( inBuf ):
# parse footnotes into a list of dictionaries with the following properties for each entry
# 	startLine - line number of [Footnote start
#	endLine - line number of last line of [Footnote] block
#	fnBlock - list of lines containing full [Footnote:]
#	fnText - list of lines containing footnote text
# 	paragraphEnd - line number of the blank line following the paragraph this footnote is located in
# 	chapterEnd - line number of the blank line following the last paragraph in the chapter this footnote is located in

	footnotes = []
	lineNum = 0

	logging.info("------ Parsing footnotes")
	while lineNum < len(inBuf):
		foundFootnote = False
		
		needsJoining = False    
		if( re.match(r"\*\[Footnote", inBuf[lineNum]) or re.search(r"\]\*$", inBuf[lineNum]) ):
			logging.info("Footnote requires joining at line {}: {}".format(lineNum,inBuf[lineNum]))
			needsJoining = True
			foundFootnote = True

		if( re.match(r"\[Footnote", inBuf[lineNum]) ):
			foundFootnote = True
		
		if( foundFootnote ):
			startLine = lineNum

			# Copy footnote block
			fnBlock = []
			fnBlock.append(inBuf[lineNum])
			while( lineNum < len(inBuf)-1 and not re.search(r"][\*]*$", inBuf[lineNum]) ):
				lineNum += 1
				fnBlock.append(inBuf[lineNum])

			endLine = lineNum

			# Find end of paragraph
			paragraphEnd = findNextEmptyLine( inBuf, lineNum )

			# Find end of chapter (line after last line of last paragraph)
			chapterEnd = findNextChapter( inBuf, lineNum )
			chapterEnd = findPreviousLineOfText( inBuf, chapterEnd ) + 1

			# Extract footnote text from [Footnote] block
			fnText = []
			for line in fnBlock:
				line = re.sub(r"^\*\[Footnote: ", "", line)
				line = re.sub(r"^\[Footnote [A-Z]: ", "", line)
				line = re.sub(r"^\[Footnote \d+: ", "", line)
				line = re.sub(r"][\*]*$", "", line)
				fnText.append(line)
			
			# Add entry
			footnotes.append({'fnBlock':fnBlock, 'fnText':fnText, 'startLine':startLine, 'endLine':endLine, 'paragraphEnd':paragraphEnd, 'chapterEnd':chapterEnd, 'needsJoining':needsJoining})

		lineNum += 1

	logging.info("--------- Parsed {} footnotes".format(len(footnotes)))

	return footnotes;


def processFootnotes( inBuf, footnoteDestination, keepOriginal ):
	outBuf = []

	logging.info("--- Processing footnotes")

	# strip empty lines before [Footnotes], *[Footnote
	lineNum = 0
	logging.info("------ Remove blank lines before [Footnotes]")
	while lineNum < len(inBuf):
		if( re.match(r"\[Footnote", inBuf[lineNum]) or re.match(r"\*\[Footnote", inBuf[lineNum]) ):
			# delete previous blank line(s)
			while( isLineBlank(outBuf[-1]) ):
				del outBuf[-1]

		outBuf.append(inBuf[lineNum])
		lineNum += 1
	inBuf = outBuf

#	for line in inBuf:
#		print(line)

	# parse footnotes into list of dictionaries
	footnotes = parseFootnotes( outBuf )
#	print(footnotes)

	# renumber footnote anchors 
	fnAnchorCount = 0
	lineNum = 0
	logging.info("------ Renumber footnote anchors [1] or [A]")
	while lineNum < len(outBuf):
		#TODO: need to handle case where there is more than one anchor on a line (use re.findall)
		m = re.search("\[([A-Z]|[0-9]+)\]", outBuf[lineNum])
		if( m ):
			fnAnchorCount += 1
			# replace [1] or [A] with [n]
			curAnchor = "\[{}\]".format(m.group(1))
			newAnchor = "[{}]".format(fnAnchorCount)
			#TODO: add option to use ppgen autonumber? [#].. unsure if good reason to do this, would hide footnote mismatch errors and increase ppgen project compile times
			logging.debug("{}: {}".format(newAnchor, outBuf[lineNum]))
			outBuf[lineNum] = re.sub( curAnchor, newAnchor, outBuf[lineNum] )
			
		lineNum += 1

	logging.info("------ Replaced {} footnote anchors".format(fnAnchorCount))
	
	# join broken footnotes
	joinCount = 0
	logging.info("------ Fixing broken footnotes")
	i = 0
	while i < len(footnotes):
		if footnotes[i]['needsJoining']:
			# TODO: can footnotes span more than two pages?
			if not footnotes[i+1]['needsJoining']:
				logging.error("*** Attempt to join footnote failed! ***")
				logging.error("*** Footnote {} ({}): {}".format(i,footnotes[i]['startLine']+1,footnotes[i]['fnBlock'][0]) )
				logging.error("*** Footnote {} ({}): {}".format(i+1,footnotes[i+1]['startLine']+1,footnotes[i+1]['fnBlock'][0]) )
			else:
				# merge fnBlock and fnText from second into first
				footnotes[i]['fnBlock'].extend(footnotes[i+1]['fnBlock'])
				footnotes[i]['fnText'].extend(footnotes[i+1]['fnText'])			
				footnotes[i]['needsJoining'] = False
				del footnotes[i+1]
				joinCount += 1

		i += 1

	logging.info("------ Joined {} broken footnotes".format(joinCount))
	logging.info("------ {} footnotes after joining".format(len(footnotes)))
	
	if( len(footnotes) != fnAnchorCount ):
		logging.error("Footnote anchor count does not match footnote count")
	
	# generate ppgen footnote markup 
	if( footnoteDestination == "bookend" ):
		fnMarkup = []
		fnMarkup.append(".pb")
		fnMarkup.append(".if t")	
		fnMarkup.append(".sp 4")
		fnMarkup.append(".ce")
		fnMarkup.append("FOOTNOTES:")
		fnMarkup.append(".sp 2")
		fnMarkup.append(".if-")
		
		fnMarkup.append(".if h")
		fnMarkup.append(".de div.footnotes { border: dashed 1px #aaaaaa; padding: 1.5em; }")
		fnMarkup.append(".li")
		fnMarkup.append('<div class="footnotes">')
		fnMarkup.append(".li-")
		fnMarkup.append(".ce")
		fnMarkup.append("<xl>FOOTNOTES:</xl>")
		fnMarkup.append(".sp 2") #TODO: current ppgen doesn't add space (pvs not applied to .fn I bet)
		fnMarkup.append(".if-")

		for i, fn in enumerate(footnotes):
			fnMarkup.append(".fn {}".format(i+1))
			for line in fn['fnText']:
				fnMarkup.append(line)
			fnMarkup.append(".fn-")
			
		fnMarkup.append(".if h")
		fnMarkup.append(".li")
		fnMarkup.append('</div>')
		fnMarkup.append(".li-")
		fnMarkup.append(".if-")

		outBuf.extend(fnMarkup)
		print("bookend")

	if( footnoteDestination == "paragraphend" ):
		print("paragraphend")

	if( footnoteDestination == "chapterend" ):
		print("chapterend")
		
	# strip [Footnote markup
	#TODO: better to do this during parsing?
	outBuf = stripFootnoteMarkup( outBuf )
	
	return outBuf


def main():
	args = docopt(__doc__, version='ppprep 0.1')

	# Process required command line arguments
	outfile = createOutputFileName( args['<infile>'] )
	if( args['<outfile>'] ):
		outfile = args['<outfile>']

	infile = args['<infile>']

	# Open source file and represent as an array of lines
	inBuf = loadFile( infile )

	# Configure logging
	logLevel = logging.INFO #default
	if( args['--verbose'] ):
		logLevel = logging.DEBUG
	elif( args['--quiet'] ):
		logLevel = logging.ERROR

	logging.basicConfig(format='%(levelname)s: %(message)s', level=logLevel)

	logging.debug(args)

	# Process processing options
	doChapterHeadings = args['--chapters'];
	doSectionHeadings = args['--sections'];
	doFootnotes = args['--footnotes'];
	doPages = args['--pages'];

	# Check that at least one processing options is set
	if( not doChapterHeadings and \
		not doSectionHeadings and \
		not doFootnotes and \
		not doPages ):
		logging.error("No processing options set; run 'ppprep -h' for a list of available options")
	else:
		# Process source document
		logging.info("Processing '" + infile + "' to '" + outfile + "'")
		outBuf = []
		inBuf = removeTrailingSpaces( inBuf )
		if( doPages ):
			outBuf = processBlankPages( inBuf, args['--keeporiginal'] )
			inBuf = outBuf
			outBuf = processPageNumbers( inBuf, args['--keeporiginal'] )
			inBuf = outBuf
		if( doChapterHeadings or doSectionHeadings ):
			outBuf = processHeadings( inBuf, doChapterHeadings, doSectionHeadings, args['--keeporiginal'] )
			inBuf = outBuf
		if( doFootnotes ):
			footnoteDestination = "bookend"
			if( args['--setfndest'] ):
				footnoteDestination = args['--setfndest']

			outBuf = processFootnotes( inBuf, footnoteDestination, args['--keeporiginal'] )
			inBuf = outBuf

		if( not args['--dryrun'] ):
			# Save file
			f = open(outfile,'w')
			for line in outBuf:
				f.write(line+'\r\n')
			f.close()

	return


if __name__ == "__main__":
	main()
