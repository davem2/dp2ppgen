#!/usr/bin/env python

"""ppprep

Usage:
  ppprep [-cdefjkpqv] [--force] [--fndest=<fndest>] <infile> [<outfile>]
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
  --fndest=<fndest>    Where to relocate footnotes (paragraphend, chapterend, bookend, inline).
  --force              Ignore markup errors and force operation.
  -j, --joinspanned    Join hypenations (-* *-) and formatting markup (/* */ /# #/) that spans page breaks
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


# Limited check for syntax errors in dp markup of input file
def validateDpMarkup( inBuf ):
	
	# TODO, someone must have written a more thorough version of this already.. use that instead
	
	logging.info("-- Checking input file for markup errors")

	inBuf = removeTrailingSpaces(inBuf)
	
	formattingStack = []	
	lineNum = 0
	errorCount = 0
	while lineNum < len(inBuf):
	

		# Detect unbalanced out-of-line formatting markup /# #/ /* */
		m = re.match(r"^\/(\*|\#)", inBuf[lineNum])
		if m:
			d = ({'ln':lineNum+1,'v':"/{}".format(m.group(1))})
			formattingStack.append(d)
			
		m = re.match(r"^(\*|\#)\/", inBuf[lineNum])
		if m:
			v = m.group(1)
			if len(formattingStack) == 0 or formattingStack[-1]['v'] != "/{}".format(v):
				errorCount += 1
				if len(formattingStack) == 0:
					logging.error("Line {}: Unexpected {}/".format(lineNum+1,v))
				else:
					logging.error("Line {}: Unexpected {}/, previous ({}:{})".format(lineNum+1,v,formattingStack[-1]['ln'],formattingStack[-1]['v']))
					logging.debug("{}".format(formattingStack))
			else:
				formattingStack.pop()


		# Check balance of <i></i>, [], {}
#		m = re.findall(r"(\[|\]|\{|\}|\(|\)|<\/?\w+>)", inBuf[lineNum])
		m = re.findall(r"(\[|\]|\{|\}|<\/?\w+>)", inBuf[lineNum])
		for v in m:
			
			if v == "<tb>": # ignore
				pass
			
			elif v == "]": # closing markup
				if len(formattingStack) == 0 or formattingStack[-1]['v'] != "[":
					errorCount += 1
					if len(formattingStack) == 0:
						logging.error("Line {}: Unexpected {}".format(lineNum+1,v))
					else:
						logging.error("Line {}: Unexpected {}, previous ({}:{})".format(lineNum+1,v,formattingStack[-1]['ln'],formattingStack[-1]['v']))
						logging.debug("{}".format(formattingStack))
				else:
					formattingStack.pop()

			elif v == "}": # closing markup
				if len(formattingStack) == 0 or formattingStack[-1]['v'] != "{":
					errorCount += 1
					if len(formattingStack) == 0:
						logging.error("Line {}: Unexpected {}".format(lineNum+1,v))
					else:
						logging.error("Line {}: Unexpected {}, previous ({}:{})".format(lineNum+1,v,formattingStack[-1]['ln'],formattingStack[-1]['v']))
						logging.debug("{}".format(formattingStack))
				else:
					formattingStack.pop()

			# Disabled as this will get false positives from diacratic markup [)x] and won't affect conversion anyways
#				if len(formattingStack) == 0 or formattingStack[-1]['v'] != "(":
#					errorCount += 1
#					if len(formattingStack) == 0:
#						logging.error("Line {}: Unexpected {}".format(lineNum+1,v))
#					else:
#						logging.error("Line {}: Unexpected {}, previous ({}:{})".format(lineNum+1,v,formattingStack[-1]['ln'],formattingStack[-1]['v']))
#						logging.debug("{}".format(formattingStack))
#				else:
#					formattingStack.pop()

			elif "/" in v: # closing markup
				v2 = re.sub("/","",v)
				if len(formattingStack) == 0 or formattingStack[-1]['v'] != v2:
					errorCount += 1
					if len(formattingStack) == 0:
						logging.error("Line {}: Unexpected {}".format(lineNum+1,v))
					else:
						logging.error("Line {}: Unexpected {}, previous ({}:{})".format(lineNum+1,v,formattingStack[-1]['ln'],formattingStack[-1]['v']))
						logging.debug("{}".format(formattingStack))
				else:
					formattingStack.pop()

			else:
				d = ({'ln':lineNum+1,'v':v})
				formattingStack.append(d)
				

		# Check for specific issues that have caused conversion issues in the past
		
		# Single line [Footnote] does not end at closing ]
		# ex. [Footnote 1: Duine, <i>Saints de Domnonée</i>, pp. 5-12].
		if re.match(r"\*?\[Footnote(.*)\]\*?.*$", inBuf[lineNum]):
			if inBuf[lineNum].count('[') - inBuf[lineNum].count(']') == 0: # ignore multiline footnotes with proofer notes or some other [] markup within them
				if not (inBuf[lineNum][-1] == ']' or inBuf[lineNum][-2:] == ']*'):
					errorCount += 1
					logging.error("Line {}: Extra characters found after closing ']' in [Footnote]\n       {}".format(lineNum+1,inBuf[lineNum]))
	
		# Extra text after out-of-line formatting markup
		# ex. /*[**new stanza?]
		if re.match(r"^(\/\*|\/\#|\*\/|\#\/).+", inBuf[lineNum]):
			errorCount += 1
			logging.error("Line {}: Extra text after out-of-line formatting markup\n       {}".format(lineNum+1,inBuf[lineNum]))
	
		lineNum += 1
			
		# Chapters
		# Sections	
		
	# Look for unresolved <i></i>, [], {}
	if len(formattingStack) > 0:
		errorCount += 1
		logging.error("Reached end of file with unresolved formatting markup, (probably due to previous markup error(s))")
		logging.debug("{}".format(formattingStack))

	
	
	
	if errorCount > 0:
		logging.info("-- Found {} markup errors".format(errorCount) )

	return errorCount
	

# Format helper function, truncate to width and indicate truncation occured with ...
def truncate( string, width ):
    if len(string) > width:
        string = string[:width-3] + '...'
    return string

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

	logging.info("-- Processing blank pages")

	while lineNum < len(inBuf):
		m = re.match(r"^\[Blank Page]", inBuf[lineNum])
		if m:
			if keepOriginal:
				outBuf.append("// *** PPPREP ORIGINAL: {}".format(inBuf[lineNum]))
			outBuf.append("// [Blank Page]")
			logging.debug("{:>{:d}}: '{}' to '{}'".format(str(lineNum+1),len(str(len(inBuf))),inBuf[lineNum],outBuf[-1]))
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

	logging.info("-- Processing page numbers")

	while lineNum < len(inBuf):
		m = re.match(r"-----File: (\d+\.png).*", inBuf[lineNum])
		if m:
			if keepOriginal:
				outBuf.append("// *** PPPREP ORIGINAL: {}".format(inBuf[lineNum]))
			outBuf.append("// {}".format(m.group(1)))
			outBuf.append(".pn +1")
			logging.debug("{:>{:d}}: '{}' to '{}, {}'".format(str(lineNum+1),len(str(len(inBuf))),inBuf[lineNum],outBuf[-2],outBuf[-1]))
			lineNum += 1

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	return outBuf;


def isLineBlank( line ):
	return re.match(r"^\s*$", line)


def isLineComment( line ):
	return re.match(r"^\/\/ *$", line)


#TODO: implement me
#def isLinePageBreak( line ):
#	return


def formatAsID( s ):
	s = re.sub(r"<\/?\w+>", "", s)  # Remove inline markup
	s = re.sub(r" ", "_", s)        # Replace spaces with underscore
	s = re.sub(r"[^\w\s]", "", s)   # Strip everything but alphanumeric and _
	s = s.lower()                   # Lowercase

	return s


def findNextEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum < len(buf)-1 and not isLineBlank(buf[lineNum]):
		lineNum += 1
	return lineNum


def findPreviousEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum >= 0 and not isLineBlank(buf[lineNum]):
		lineNum -= 1
	return lineNum


def findNextNonEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum < len(buf)-1 and isLineBlank(buf[lineNum]):
		lineNum += 1
	return lineNum


def findPreviousNonEmptyLine( buf, startLine ):
	lineNum = startLine
	while lineNum >= 0 and isLineBlank(buf[lineNum]):
		lineNum -= 1
	return lineNum


# find previous line that contains original book text (ignore ppgen markup, proofing markup, blank lines)
def findPreviousLineOfText( buf, startLine ):
	lineNum = findPreviousNonEmptyLine(buf, startLine)
	while lineNum > 0 and re.match(r"[\.\*\#\/\[]", buf[lineNum]):
		lineNum = findPreviousNonEmptyLine(buf, lineNum-1)
	return lineNum


# find next line that contains original book text (ignore ppgen markup, proofing markup, blank lines)
def findNextLineOfText( buf, startLine ):
	lineNum = findNextNonEmptyLine(buf, startLine)
	while lineNum < len(buf)-1 and re.match(r"(\.[a-z0-9]{2} |[\*\#]\/|\/[\*\#]|\[\w+|\/\/)", buf[lineNum]):
		lineNum = findNextNonEmptyLine(buf, lineNum+1)
	return lineNum


def findNextChapter( buf, startLine ):
	lineNum = startLine
	while lineNum < len(buf)-1 and not re.match(r"\.h2", buf[lineNum]):
		lineNum += 1
	return lineNum
		

def processHeadings( inBuf, doChapterHeadings, doSectionHeadings, keepOriginal ):
	outBuf = []
	lineNum = 0
	consecutiveEmptyLineCount = 0
	rewrapLevel = 0
	foundChapterHeadingStart = False

	if doChapterHeadings and doSectionHeadings:
		logging.info("-- Processing chapter and section headings")
	if doChapterHeadings:
		logging.info("-- Processing chapter headings")
	if doSectionHeadings:
		logging.info("-- Processing section headings")

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

		# Detect when inside out-of-line formatting block /# #/ /* */
		if re.match(r"^\/\*", inBuf[lineNum]) or re.match(r"^\/\#", inBuf[lineNum]):
			rewrapLevel += 1
		elif re.match(r"^\*\/", inBuf[lineNum]) or re.match(r"^\#\/", inBuf[lineNum]):
			rewrapLevel -= 1

		# Chapter heading
		if doChapterHeadings and consecutiveEmptyLineCount == 4 and not isLineBlank(inBuf[lineNum]) and rewrapLevel == 0:
			inBlock = []
			outBlock = []
			foundChapterHeadingEnd = False;
			consecutiveEmptyLineCount = 0;

			# Copy chapter heading block to inBlock
			while lineNum < len(inBuf) and not foundChapterHeadingEnd:
				if isLineBlank(inBuf[lineNum]):
					consecutiveEmptyLineCount += 1
					if consecutiveEmptyLineCount == 2:
						foundChapterHeadingEnd = True
						consecutiveEmptyLineCount = 0
				else:
					consecutiveEmptyLineCount = 0

				# chapters don't span pages
				if re.match(r"\/\/ (\d+)\.[png|jpg|jpeg]", inBuf[lineNum]):
					foundChapterHeadingEnd = True

				if foundChapterHeadingEnd:
					# Remove empty lines from end of chapter heading block
					while isLineBlank(inBlock[-1]):
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

			outBlock.append("")
			outBlock.append("// ******** PPPREP GENERATED ****************************************")
			outBlock.append(".sp 4")
			outBlock.append(".h2 id={}".format(chapterID))
			outBlock.append(chapterLine)
			outBlock.append(".sp 2")

			if keepOriginal:
				# Write out original as a comment
				outBlock.append(".ig  // *** PPPREP BEGIN ORIGINAL ***********************************")
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
			logging.info("--- .h2 {}".format(chapterLine))

		# Section heading
		elif doSectionHeadings and consecutiveEmptyLineCount == 2 and not isLineBlank(inBuf[lineNum]) and rewrapLevel == 0:
			inBlock = []
			outBlock = []
			foundSectionHeadingEnd = False;
			consecutiveEmptyLineCount = 0;

			# Copy section heading block to inBlock
			while lineNum < len(inBuf) and not foundSectionHeadingEnd:
				if isLineBlank(inBuf[lineNum]):
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

			outBlock.append("// ******** PPPREP GENERATED ****************************************")
			outBlock.append(".sp 2")
			outBlock.append(".h3 id={}".format(sectionID))
			outBlock.append(sectionLine)
			outBlock.append(".sp 1")

			if keepOriginal:
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
			logging.info("--- .h3 {}".format(sectionID))
		else:
			if isLineBlank(inBuf[lineNum]):
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
		logging.critical("specified file {} not found".format(fn))
		exit(1)

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
	outfile = "{}-out.txt".format(infile.split('.')[0]) 
	return outfile

def stripFootnoteMarkup( inBuf ):
	outBuf = []
	lineNum = 0
	
	while lineNum < len(inBuf):
		# copy inBuf to outBuf throwing away all footnote markup [Footnote...]
		if re.match(r"[\*]*\[Footnote", inBuf[lineNum]):
			while lineNum < len(inBuf) and not re.search(r"][\*]*$", inBuf[lineNum]):
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
# 	scanPageNumber - scan page this footnote is located on

	footnotes = []
	lineNum = 0
	currentScanPage = 0;

	logging.info("--- Parsing footnotes")
	while lineNum < len(inBuf):
		foundFootnote = False
		
		# Keep track of active scanpage
		m = re.match(r"\/\/ (\d+)\.[png|jpg|jpeg]", inBuf[lineNum])
		if m:
			currentScanPage = m.group(1)
#			logging.debug("Processing page "+currentScanPage)

		if re.match(r"\*?\[Footnote", inBuf[lineNum]):
			foundFootnote = True
		
		if foundFootnote:
			startLine = lineNum

			# Copy footnote block
			fnBlock = []
			fnBlock.append(inBuf[lineNum])
			while lineNum < len(inBuf)-1 and not re.search(r"][\*]*$", inBuf[lineNum]):
				lineNum += 1
				fnBlock.append(inBuf[lineNum])

			endLine = lineNum

			# Is footnote part of a multipage footnote?
			needsJoining = False    
			if re.match(r"\*\[Footnote", fnBlock[0]) or re.search(r"\]\*$", fnBlock[-1]):
				logging.debug("Footnote requires joining at line {}: {}".format(lineNum+1,inBuf[lineNum]))
				needsJoining = True
				foundFootnote = True

			# Find end of paragraph
			paragraphEnd = -1 # This must be done during footnote anchor processing as paragraph end is relative to anchor and not [Footnote] markup
			# Find end of chapter (line after last line of last paragraph)
			chapterEnd = -1 # This must be done during footnote anchor processing as chapter end is relative to anchor and not [Footnote] markup

			# Extract footnote ID
			m = re.search(r"^\[Footnote (\w{1,2}):", fnBlock[0])
			if m:
				fnID = m.group(1);

			# Extract footnote text from [Footnote] block
			fnText = []
			for line in fnBlock:
				line = re.sub(r"^\*\[Footnote: ", "", line)
				line = re.sub(r"^\[Footnote [A-Z]: ", "", line)
				line = re.sub(r"^\[Footnote \d+: ", "", line)
				line = re.sub(r"][\*]*$", "", line)
				fnText.append(line)
			
			# Add entry
			footnotes.append({'fnBlock':fnBlock, 'fnText':fnText, 'fnID':fnID, 'startLine':startLine, 'endLine':endLine, 'paragraphEnd':paragraphEnd, 'chapterEnd':chapterEnd, 'needsJoining':needsJoining, 'scanPageNum':currentScanPage})

		lineNum += 1

	logging.info("--- Parsed {} footnotes".format(len(footnotes)))

#	print(footnotes)

	# Join footnotes marked above during parsing
	joinCount = 0
	i = 0
	while i < len(footnotes):
		if footnotes[i]['needsJoining']:
			if joinCount == 0:
				logging.info("--- Joining footnotes")
			
			# debug message
			logging.debug("Merging footnote [{}]".format(i+1))
			if len(footnotes[i]['fnBlock']) > 1:
				logging.debug("  ScanPg {}: {} ... {} ".format(footnotes[i]['scanPageNum'], footnotes[i]['fnBlock'][0], footnotes[i]['fnBlock'][-1]))
			else:
				logging.debug("  ScanPg {}: {}".format(footnotes[i]['scanPageNum'], footnotes[i]['fnBlock'][0]))
			if len(footnotes[i+1]['fnBlock']) > 1:
				logging.debug("  ScanPg {}: {} ... {} ".format(footnotes[i+1]['scanPageNum'], footnotes[i+1]['fnBlock'][0], footnotes[i+1]['fnBlock'][-1]))
			else:
				logging.debug("  ScanPg {}: {}".format(footnotes[i+1]['scanPageNum'], footnotes[i+1]['fnBlock'][0]))
				
			# TODO: can footnotes span more than two pages?
			if not footnotes[i+1]['needsJoining']:
				logging.error("Attempt to join footnote failed!")
				logging.error("ScanPg {} Footnote {} ({}): {}".format(footnotes[i]['scanPageNum'], i,footnotes[i]['startLine']+1,footnotes[i]['fnBlock'][0]))
				logging.error("ScanPg {} Footnote {} ({}): {}".format(footnotes[i+1]['scanPageNum'], i+1,footnotes[i+1]['startLine']+1,footnotes[i+1]['fnBlock'][0]))
			else:
				# merge fnBlock and fnText from second into first
				footnotes[i]['fnBlock'].extend(footnotes[i+1]['fnBlock'])
				footnotes[i]['fnText'].extend(footnotes[i+1]['fnText'])			
				footnotes[i]['needsJoining'] = False
				del footnotes[i+1]
				joinCount += 1

		i += 1

	if joinCount > 0:
		logging.info("--- Merged {} broken footnote(s)".format(joinCount))
	logging.info("--- {} total footnotes after joining".format(len(footnotes)))
	

	return footnotes;


def processFootnoteAnchors( inBuf, footnotes ):
	
	outBuf = inBuf
	
	# process footnote anchors 
	fnAnchorCount = 0
	lineNum = 0
	currentScanPage = 0
	currentScanPageLabel = ""
	fnIDs = []
#	r = []
	logging.info("--- Processing footnote anchors")
	while lineNum < len(outBuf):
		
		# Keep track of active scanpage
		m = re.match(r"\/\/ (\d+)\.[png|jpg|jpeg]", outBuf[lineNum])
		if m:
			currentScanPage = m.group(1)
			currentScanPageLabel = re.sub(r"\/\/ ","", outBuf[lineNum])
#			logging.debug("--- Processing page "+currentScanPage)

			# Make list of footnotes found on this page
			fnIDs = []
			for fn in footnotes:
				if fn['scanPageNum'] == currentScanPage:
					fnIDs.append(fn['fnID'])
				
			# Build regex for footnote anchors that can be found on this scanpage
#			if len(fnIDs) > 0:
#				r = "|".join(fnIDs)
#				r = r"\[({})\]".format(r)

#		print("{}: {}".format(lineNum,outBuf[lineNum]))
		m = re.findall("\[([A-Za-z]|[0-9]{1,2})\]", outBuf[lineNum])
		for anchor in m:
			# Check that anchor found belongs to a footnote on this page
			if not anchor in fnIDs:
				logging.error("No matching footnote for anchor [{}] on scan page {} (line {} in output file):\n       {}".format(anchor,currentScanPage,lineNum+1,outBuf[lineNum]))
				logging.debug(fnIDs)
				
			else:
				fnAnchorCount += 1
				# replace [1] or [A] with [n]
				curAnchor = "\[{}\]".format(anchor)
				newAnchor = "[{}]".format(fnAnchorCount)
				#TODO: add option to use ppgen autonumber? [#].. unsure if good reason to do this, would hide footnote mismatch errors and increase ppgen project compile times
				
				logging.debug("{:>5s}: ({}|{}) ... {} ...".format(newAnchor,lineNum+1,currentScanPageLabel,outBuf[lineNum]))
				for line in footnotes[fnAnchorCount-1]['fnText']:
					logging.debug("       {}".format(line))
				
				# sanity check (anchor and footnote should be on same scan page)
#				if currentScanPage != footnotes[fnAnchorCount-1]['scanPageNum']:
#					logging.warning("Anchor found on different scan page, anchor({}) and footnotes({}) may be out of sync".format(currentScanPage,footnotes[fnAnchorCount-1]['scanPageNum'])) 

				# replace anchor
				outBuf[lineNum] = re.sub(curAnchor, newAnchor, outBuf[lineNum])		
				
				# update paragraphEnd and chapterEnd so they are relative to anchor and not [Footnote
				# Find end of paragraph
				paragraphEnd = findNextEmptyLine(outBuf, lineNum)
				footnotes[fnAnchorCount-1]['paragraphEnd'] = paragraphEnd

				# Find end of chapter (line after last line of last paragraph)
				chapterEnd = findNextChapter(outBuf, lineNum)
				chapterEnd = findPreviousLineOfText(outBuf, chapterEnd) + 1
				footnotes[fnAnchorCount-1]['chapterEnd'] = chapterEnd
			
		lineNum += 1

	logging.info("--- Processed {} footnote anchors".format(fnAnchorCount))
	
	return outBuf, fnAnchorCount


def processFootnotes( inBuf, footnoteDestination, keepOriginal ):
	outBuf = []

	logging.info("-- Processing footnotes")

	# strip empty lines before [Footnotes], *[Footnote
	lineNum = 0
	logging.info("--- Remove blank lines before [Footnotes]")
	while lineNum < len(inBuf):
		if re.match(r"\[Footnote", inBuf[lineNum]) or re.match(r"\*\[Footnote", inBuf[lineNum]):
			# delete previous blank line(s)
			while isLineBlank(outBuf[-1]):
				del outBuf[-1]

		outBuf.append(inBuf[lineNum])
		lineNum += 1
	inBuf = outBuf

	# parse footnotes into list of dictionaries
	footnotes = parseFootnotes(outBuf)

	# strip [Footnote markup
	outBuf = stripFootnoteMarkup(outBuf)
	
	# find and markup footnote anchors 
	outBuf, fnAnchorCount = processFootnoteAnchors(outBuf, footnotes)
	
	if len(footnotes) != fnAnchorCount:
		logging.error("Footnote anchor count does not match footnote count")
	
	if len(footnotes) > 0:
		outBuf = generatePpgenFootnoteMarkup(outBuf, footnotes, footnoteDestination)
	
	return outBuf


# Generate ppgen footnote markup 
def generatePpgenFootnoteMarkup( inBuf, footnotes, footnoteDestination ):
	
	outBuf = inBuf
	
	if footnoteDestination == "bookend":
		logging.info("--- Adding ppgen style footnotes to end of book")
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

	elif footnoteDestination == "chapterend":
		logging.info("--- Adding ppgen style footnotes to end of chapters")	
		curChapterEnd = footnotes[-1]['chapterEnd']
		fnMarkup = []
		for i, fn in reversed(list(enumerate(footnotes))):
			
			if curChapterEnd != fn['chapterEnd']:
				# finish off last group
				outBuf.insert(curChapterEnd, ".fm")
				curChapterEnd = fn['chapterEnd']

			# build markup for this footnote
#			print("{} {}".format(fn['chapterEnd'],fn['fnText'][0]))
			fnMarkup.append(".fn {}".format(i+1))
			for line in fn['fnText']:
				fnMarkup.append(line)
			fnMarkup.append(".fn-")
			
			# insert it
			outBuf[curChapterEnd:curChapterEnd] = fnMarkup
			fnMarkup = []

		# finish off last group
		outBuf.insert(curChapterEnd, ".fm")

	elif footnoteDestination == "paragraphend":
		logging.info("--- Adding ppgen style footnotes to end of paragraphs")
		curParagraphEnd = footnotes[-1]['paragraphEnd']
		fnMarkup = []
		for i, fn in reversed(list(enumerate(footnotes))):
			
			if curParagraphEnd != fn['paragraphEnd']:
				# finish off last group
				outBuf.insert(curParagraphEnd, ".fm")
				curParagraphEnd = fn['paragraphEnd']

			# build markup for this footnote
#			print("{} {}".format(fn['paragraphEnd'],fn['fnText'][0]))
			fnMarkup.append(".fn {}".format(i+1))
			for line in fn['fnText']:
				fnMarkup.append(line)
			fnMarkup.append(".fn-")
			
			# insert it
			outBuf[curParagraphEnd:curParagraphEnd] = fnMarkup
			fnMarkup = []

		# finish off last group
		outBuf.insert(curParagraphEnd, ".fm")

	return outBuf



def joinSpannedFormatting( inBuf, keepOriginal ):
	outBuf = []

	logging.info("-- Joining spanned out-of-line formatting markup")

	# Find:
	# 1: */
	# 2: // 010.png
	# 3: 
	# 4: /*
	
	# Replace with:
	# 2: // 010.png
	# 3: 

	lineNum = 0
	joinCount = 0
	while lineNum < len(inBuf):
		joinWasMade = False
		
		m = re.match(r"^(\*\/|\#\/)$", inBuf[lineNum])
		if m:
			outBlock = []
			ln = lineNum + 1
			joinEndLineRegex = r"^\/\{}$".format(m.group(1)[0])
			while ln < len(inBuf) and isLineBlank(inBuf[ln]):
				outBlock.append(inBuf[ln])
				ln += 1

			if ln < len(inBuf) and re.match(r"\/\/ (\d+)\.[png|jpg|jpeg]", inBuf[ln]):
				outBlock.append(inBuf[ln])
				ln += 1
				while ln < len(inBuf) and isLineBlank(inBuf[ln]) or re.match(r".pn",inBuf[ln]) or re.match(r"\/\/",inBuf[ln]):
					outBlock.append(inBuf[ln])
					ln += 1
				
				if re.match(joinEndLineRegex, inBuf[ln]):
					for line in outBlock:
						outBuf.append(line)
					joinWasMade = True
					joinCount += 1
					logging.debug("Lines {}, {}: Joined spanned markup /{} {}/".format(lineNum,ln,m.group(1)[0],m.group(1)[0]))
					lineNum = ln + 1
			
		if not joinWasMade:
			outBuf.append(inBuf[lineNum])
			lineNum += 1
		
	logging.info("-- Joined {} instances of spanned out-of-line formatting markup".format(joinCount))
	return outBuf


def joinSpannedHyphenations( inBuf, keepOriginal ):
	outBuf = []

	logging.info("-- Joining spanned hyphenations")

	# Find:
	# 1: the last word on this line is cont-*
	# 2: // 010.png
	# 3: *-inued. on the line below
	
	# Replace with:
	# 1: the last word on this line is cont-**inued. 
	# 2: // 010.png
	# 3: on the line below

	lineNum = 0
	joinCount = 0
	while lineNum < len(inBuf):
		joinWasMade = False
		
		if re.search(r"\-\*$", inBuf[lineNum]) and re.match(r"\/\/ (\d+)\.[png|jpg|jpeg]", inBuf[lineNum+1]):
			ln = findNextLineOfText(inBuf,lineNum+1)
			if inBuf[ln][0] == '*':
				# Remove first word from last line (secondPart) and join append it to first line
#				secondPart = (inBuf[ln].split(' ',1)[0])[1:] # strip first word with leading * removed
				secondPart = inBuf[ln].split(' ',1)[0] 
				inBuf[ln] = inBuf[ln].split(' ',1)[1]
				inBuf[lineNum] = inBuf[lineNum] + secondPart
				logging.debug("Line {}: Resolved hyphenation, ... '{}'".format(lineNum+1,inBuf[lineNum][-30:]))	
#				logging.info("Line {}: Resolved hyphenation\n      '{}'".format(lineNum+1,inBuf[lineNum]))	
				joinCount += 1
			else:
				logging.error("Line {}: Unresolved hyphenation\n       {}\n       {}".format(lineNum+1,inBuf[lineNum],inBuf[ln]))	

		outBuf.append(inBuf[lineNum])
		lineNum += 1
		
	logging.info("-- Joined {} instances of spanned hyphenations".format(joinCount))
	return outBuf


def main():
	args = docopt(__doc__, version='ppprep 0.1')

	# Process required command line arguments
	outfile = createOutputFileName(args['<infile>'])
	if args['<outfile>']:
		outfile = args['<outfile>']

	infile = args['<infile>']

	# Open source file and represent as an array of lines
	inBuf = loadFile(infile)

	# Configure logging
	logLevel = logging.INFO #default
	if args['--verbose']:
		logLevel = logging.DEBUG
	elif args['--quiet']:
		logLevel = logging.ERROR

	logging.basicConfig(format='%(levelname)s: %(message)s', level=logLevel)

	logging.debug(args)

	# Process processing options
	doChapterHeadings = args['--chapters'];
	doSectionHeadings = args['--sections'];
	doFootnotes = args['--footnotes'];
	doPages = args['--pages'];
	doJoinSpanned = args['--joinspanned'];

	# Use default options if no processing options are set
	if not doChapterHeadings and \
		not doSectionHeadings and \
		not doFootnotes and \
		not doPages and \
		not doJoinSpanned:
		
		logging.info("No processing options were given, using default set of options -pcfj\n      Run 'ppprep -h' for a full list of options")
		doPages = True
		doChapterHeadings = True
		doFootnotes = True
		doJoinSpanned = True

	# Process source document
	logging.info("Processing '{}'".format(infile))
	outBuf = []
	inBuf = removeTrailingSpaces(inBuf)

	errorCount = validateDpMarkup(inBuf)
	if errorCount > 0 and not args['--force']:
		logging.critical("Correct markup issues then re-run operation, or use --force to ignore markup errors")
	
	else:
		if doPages or doJoinSpanned or doChapterHeadings or doSectionHeadings or doFootnotes:
			outBuf = processBlankPages(inBuf, args['--keeporiginal'])
			inBuf = outBuf
			outBuf = processPageNumbers(inBuf, args['--keeporiginal'])
			inBuf = outBuf
		if doJoinSpanned:
			outBuf = joinSpannedFormatting(inBuf, args['--keeporiginal'])
			inBuf = outBuf
			outBuf = joinSpannedHyphenations(inBuf, args['--keeporiginal'])
			inBuf = outBuf
		if doChapterHeadings or doSectionHeadings:
			outBuf = processHeadings(inBuf, doChapterHeadings, doSectionHeadings, args['--keeporiginal'])
			inBuf = outBuf
		if doFootnotes:
			footnoteDestination = "bookend"
			if args['--fndest']:
				footnoteDestination = args['--fndest']
			outBuf = processFootnotes(inBuf, footnoteDestination, args['--keeporiginal'])
			inBuf = outBuf
			
		if not args['--dryrun']:
			logging.info("Saving output to '{}'".format(outfile))
			# Save file
			f = open(outfile,'w')
			for line in outBuf:
				f.write(line+'\n')
			f.close()

	return


if __name__ == "__main__":
	main()
