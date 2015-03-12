#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""dp2ppgen

Usage:
  dp2ppgen [options] <infile> [<outfile>]
  dp2ppgen -h | --help
  dp2ppgen --version

Translates pgdp.org formatted text files into ppgen syntax.

Examples:
  dp2ppgen book.txt
  dp2ppgen book.txt book-src.txt

Options:
  -c, --chapters       Convert chapter headings into ppgen style chapter headings.
  -d, --dryrun         Run through conversions but do not write out result.
  -e, --sections       Convert section headings into ppgen style section headings.
  -f, --footnotes      Convert footnotes into ppgen format.
  --fndest=<fndest>    Where to relocate footnotes (paragraphend, chapterend, bookend, inline).
  --fixup              Perform guiguts style fixup operations.
  --force              Ignore markup errors and force operation.
  -j, --joinspanned    Join hypenations (-* *-) and formatting markup (/* */ /# #/) that spans page breaks
  -k, --keeporiginal   On any conversion keep original text as a comment.
  -p, --pages          Convert page breaks into ppgen // 001.png style, add .pn statements and comment out [Blank Page] lines.
  -q, --quiet          Print less text.
  -s, --sidenotes      Convert sidenotes into ppgen format.
  -t, --tables		   Convert tables into HTML.
  -v, --verbose        Print more text.
  -h, --help           Show help.
  --utf8               Convert characters to UTF8
  --version            Show version.
"""

from docopt import docopt
import glob
import re
import os
import sys
import logging
import tempfile
import subprocess


VERSION="0.1.0" # MAJOR.MINOR.PATCH | http://semver.org


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
			else:
				formattingStack.pop()


#		# Check balance of [], {}, (), <i></i>
#		m = re.findall(r"(\[|\]|\{|\}|\(|\)|<\/?\w+>)", inBuf[lineNum])

#		# Check balance of [], {}, <i></i>
#		m = re.findall(r"(\[|\]|\{|\}|<\/?\w+>)", inBuf[lineNum])

		# Check balance of [], <i></i>
		m = re.findall(r"(\[|\]|<\/?\w+>)", inBuf[lineNum])
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
				else:
					formattingStack.pop()

#			elif v == "}": # closing markup
#				if len(formattingStack) == 0 or formattingStack[-1]['v'] != "{":
#					errorCount += 1
#					if len(formattingStack) == 0:
#						logging.error("Line {}: Unexpected {}".format(lineNum+1,v))
#					else:
#						logging.error("Line {}: Unexpected {}, previous ({}:{})".format(lineNum+1,v,formattingStack[-1]['ln'],formattingStack[-1]['v']))
#						logging.debug("{}".format(formattingStack))
#				else:
#					formattingStack.pop()

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

		if errorCount == 1:
			logging.error("Unresolved markup:")
			s = "Line {}: '{}'".format(formattingStack[0]['ln'],formattingStack[0]['v'])
			for v in formattingStack[1:]:
				s += ", Line {}: '{}'".format(v['ln'],v['v'])
			logging.error(s)
		else:
			logging.debug(formattingStack)

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
	count = 0

	logging.info("-- Processing blank pages")

	while lineNum < len(inBuf):
		m = re.match(r"^\[Blank Page]", inBuf[lineNum])
		if m:
			if keepOriginal:
				outBuf.append("// *** DP2PPGEN ORIGINAL: {}".format(inBuf[lineNum]))
			outBuf.append("// [Blank Page]")
			logging.debug("{:>{:d}}: '{}' to '{}'".format(str(lineNum+1),len(str(len(inBuf))),inBuf[lineNum],outBuf[-1]))
			lineNum += 1
			count += 1

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	logging.info("-- Processed {} blank pages".format(count))

	return outBuf;


# Replace : -----File: 001.png---\sparkleshine\swankypup\Kipling\SeaRose\Scholar\------
# with    : // 001.png
def processPageNumbers( inBuf, keepOriginal ):
	outBuf = []
	lineNum = 0
	count = 0

	logging.info("-- Processing page numbers")

	while lineNum < len(inBuf):
		m = re.match(r"-----File: (\d+\.(png|jpg|jpeg)).*", inBuf[lineNum])
		if m:
			if keepOriginal:
				outBuf.append("// *** DP2PPGEN ORIGINAL: {}".format(inBuf[lineNum]))
			s = ".bn {0} // -----------------------( {0} )".format(m.group(1))
			outBuf.append("{0}{1}".format(s,'-'*max(72-len(s),0)))
			outBuf.append(".pn +1")
			logging.debug("{:>{:d}}: '{}' to '{}, {}'".format(str(lineNum+1),len(str(len(inBuf))),inBuf[lineNum],outBuf[-2],outBuf[-1]))
			lineNum += 1
			count += 1

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	logging.info("-- Processed {} page numbers".format(count))

	return outBuf;


def isLineBlank( line ):
	return re.match(r"^\s*$", line)


def isLineComment( line ):
	return re.match(r"^\/\/*$", line)


def isLinePageBreak( line ):
	return (parseScanPage(line) != None)

def parseScanPage( line ):
	scanPageNum = None

	m = re.match(r"-----File: (\d+\.(png|jpg|jpeg)).*", line)
	if m:
		scanPageNum = m.group(1)

	m = re.match(r"\/\/ (\d+\.(png|jpg|jpeg))", line)
	if m:
		scanPageNum = m.group(1)

	m = re.match(r"\.bn (\d+\.(png|jpg|jpeg))", line)
	if m:
		scanPageNum = m.group(1)

	return scanPageNum


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
	while lineNum < len(buf)-1 and re.match(r"(\.[a-z0-9]{2} |[\*\#]\/|\/[\*\#]|\*?\[\w+|\/\/)", buf[lineNum]):
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
	chapterCount = 0
	sectionCount = 0

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
				if isLinePageBreak(inBuf[lineNum]):
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
			if keepOriginal:
				outBlock.append("// ******** DP2PPGEN GENERATED ****************************************")
			outBlock.append(".sp 4")
			outBlock.append(".h2 id={}".format(chapterID))
			outBlock.append(chapterLine)
			outBlock.append(".sp 2")

			if keepOriginal:
				# Write out original as a comment
				outBlock.append(".ig  // *** DP2PPGEN BEGIN ORIGINAL ***********************************")
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
			chapterCount += 1

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

			if keepOriginal:
				outBlock.append("// ******** DP2PPGEN GENERATED ****************************************")
			outBlock.append(".sp 2")
			outBlock.append(".h3 id={}".format(sectionID))
			outBlock.append(sectionLine)
			outBlock.append(".sp 1")

			if keepOriginal:
				# Write out original as a comment
				outBlock.append(".ig  // *** DP2PPGEN BEGIN ORIGINAL ***********************************")
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
			sectionCount += 1

		else:
			if isLineBlank(inBuf[lineNum]):
				consecutiveEmptyLineCount += 1
			else:
				consecutiveEmptyLineCount = 0

			outBuf.append(inBuf[lineNum])
			lineNum += 1

	if doChapterHeadings:
		logging.info("-- Processed {} chapters".format(chapterCount))

	if doSectionHeadings:
		logging.info("-- Processed {} sections".format(sectionCount))

	return outBuf;


def processTables( inBuf, keepOriginal ):
	outBuf = []
	lineNum = 0
	foundChapterHeadingStart = False
	tableCount = 0

	logging.info("-- Processing tables")

	while lineNum < len(inBuf):
		# Find next /*
		if re.match(r"^\/\*", inBuf[lineNum]):
			inBlock = []
			outBlock = []
			foundChapterHeadingEnd = False;
			consecutiveEmptyLineCount = 0;

			#TODO use guiguts style markup
			isTable = False
			if re.match(r"^\/\*TABLE", inBuf[lineNum]):
				isTable = True

			# Copy potential table to inBlock
			lineNum += 1
			while lineNum < len(inBuf) and not re.match(r"\*\/", inBuf[lineNum]):
				inBlock.append(inBuf[lineNum])
				lineNum += 1
			lineNum += 1

			# Use autodetect if /* isnt marked
			if not isTable:
				isTable = detectTable(inBlock)

			if isTable:
				# Log action
				logging.info("\n----- Found table:")
				for line in inBlock:
					logging.info(line)
				tableCount += 1

				# Correct markup for rst, warn about things that need manual intervention
				rstBlock = dpTableToRst(inBlock)

				# Run through rst2html
				tableHTML = rstTableToHTML(rstBlock)

				# Build ppgen code
				outBlock.append(".if t")
				outBlock.append(".nf b")
				for line in inBlock:
					outBlock.append(line)
				outBlock.append(".nf-")
				outBlock.append(".if-")
				outBlock.append(".if h")
				outBlock.append(".li")
				for line in tableHTML:
					outBlock.append(line)
				outBlock.append(".li-")
				outBlock.append(".if-")

				# Write out chapter heading block
				for line in outBlock:
					outBuf.append(line)

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	logging.info("-- Processed {} tables".format(tableCount))

	# Add table CSS
	if tableCount > 0:
		cssBlock = []
		cssBlock.append("// Tables")
		cssBlock.append(".de .tableU1 { page-break-inside: avoid; margin: 1.5em auto; border-collapse: collapse; width: auto; max-width: 97%}")
		cssBlock.append(".de .tableU1 td, .tableU1 th { padding: 0.15em 0.5em; border-left: 1px solid black; border-right: 1px solid black; border-bottom: 1px solid black; text-align: center; font-size: small; }")
		cssBlock.append(".de .tableU1 th { padding: 0.8em 0.5em; font-weight: normal; font-size: smaller; border: 1px solid black; }")
		cssBlock.append(".de .tableU1 td div.lgcurly { font-size:300%;font-weight:lighter;margin:0;line-height:1em;text-indent:0; }")
		cssBlock.append("")
		cssBlock.append(".de caption { margin-bottom: 0.8em; font-weight: bold; font-size: 0.9em; }")
		cssBlock.append(".de td.ybt, th.ybt { border-top: 1px solid black; }")
		cssBlock.append(".de td.nbt, th.nbt { border-top-style: none; }")
		cssBlock.append(".de td.nbb, th.nbb { border-bottom-style: none; }")
		cssBlock.append(".de td.nbl, th.nbl { border-left-style: none; }")
		cssBlock.append(".de td.nbr, th.nbr { border-right-style: none; }")
		cssBlock.append(".de td.dbt, th.dbt { border-top: double; }")
		cssBlock.append(".de td.dbb, th.dbb { border-bottom: double; }")
		cssBlock.append(".de td.dbr, th.dbr { border-right: double; }")
		cssBlock.append(".de td.valignb, th.valignb { vertical-align: bottom; }")
		cssBlock.append(".de td.left { text-align: left; }")
		cssBlock.append(".de td.right { text-align: right; }")
		cssBlock.append(".de td.hang { text-align: left; padding-left: 1.5em; text-indent: -1.2em; }")
		cssBlock.append(".de td.hang2 { text-align: left; padding-left: 3em; text-indent: -1.2em; }")
		cssBlock.append(".de .nodecoration { text-decoration: none; }")
		cssBlock.append("")

		outBuf[0:0] = cssBlock

	return outBuf;


def rstTableToHTML( inBuf ):

	# Build input to rstToHtml
	inFile = tempfile.NamedTemporaryFile(delete=False)
	inFileName=inFile.name
	for line in inBuf:
		inFile.write(bytes(line+'\n', 'UTF-8'))
	inFile.close()

	# Process table with rst2html
	outFileName=makeTempFile()
	commandLine=['rst2html',inFileName,outFileName]
	logging.debug("commandLine:{}".format(str(commandLine)))
	proc=subprocess.Popen(commandLine)
	proc.wait()
	if( proc.returncode != 0 ):
		logging.error("Command failed: {}".format(str(commandLine)))

	# Parse table HTML from rst2html output
	outBuf = []
	inTable = False
	for line in loadFile(outFileName):
		if "<table" in line:
			line = '<table class="tableU1">'
			inTable = True

		if "</table" in line:
			outBuf.append(line)
			inTable = False

		if inTable:
			outBuf.append(line)

	# Compact rows, strip colgroup, tbody
	inBuf = outBuf[:]
	outBuf = []
	inTr = False
	inColgroup = False
	rowStart = 0
	for i, line in enumerate(inBuf):
		if "<colgroup" in line:
			inColgroup = True
		elif "<tr" in line:
			inTr = True
			rowStart = i

		if "</tr" in line:
			rowHTML = ' '.join(inBuf[rowStart:i])
			outBuf.append(rowHTML)
			inTr = False
		if "</colgroup" in line:
			inColgroup = False
		elif not inTr and not inColgroup:
			outBuf.append(line)

	# Strip tbody
	inBuf = outBuf[:]
	outBuf = []
	for i, line in enumerate(inBuf):
		if not re.match("</?tbody",line):
			outBuf.append(line)

	# Assume first row is header row
	done = False
	for i, line in enumerate(outBuf):
		if "<tr" in line and not done:
			outBuf[i] = outBuf[i].replace("<td","<th")
			outBuf[i] = outBuf[i].replace("</td>","</th>")
			done = True

	return outBuf


def makeTempFile():
    tf = tempfile.NamedTemporaryFile(delete=False)
    fn = tf.name
    tf.close()
    return fn


def dpTableToRst( inBuf ):
	outBuf = inBuf[:]
	tableWidth = 0

	# Trim whitespace
	for i, line in enumerate(outBuf):
		outBuf[i] = outBuf[i].rstrip()

	# Add left/right edges if needed
	inTable = False
	for i, line in enumerate(outBuf):

		if re.match(r"\+-",line):
			inTable = True
		elif re.match(r"-",line):
			outBuf[i] = "+{}".format(outBuf[i])
			inTable = True
		elif re.match(r"[^|+]",line) and inTable:
			outBuf[i] = "|{}".format(outBuf[i])
		if re.search(r"-$",line):
			outBuf[i] = "{}+".format(outBuf[i])
			tableWidth = len(outBuf[i])
		elif re.search(r"[^|+]$",line) and inTable or tableWidth > len(outBuf[i]):
			if tableWidth > len(outBuf[i]):
				s = "{0:<{tableWidth}}|".format(outBuf[i],tableWidth=(tableWidth-1))
				outBuf[i] = s
			else:
				outBuf[i] = "{}|".format(outBuf[i])

		# Left align cell text
		m = re.findall(r"\|([^|+]+)",outBuf[i])
		for cell in m:
			cw = len(cell)
			if re.search(r"[^|\s]",cell):
				s = r"|{}".format(cell)
				r = r"|{0:<{cw}}".format(cell.lstrip(),cw=cw)
				outBuf[i] = outBuf[i].replace(s,r)

		# Ignore lines not inside table (title etc.)
		if not inTable and line != "":
			logging.warn("Ignoring line outside table:\n{}".format(line))
			del outBuf[i]

	return outBuf


def detectTable( buf ):
	matches = {
			  "--------+": False,
			  "|": False,
			  "T[aAbBlLeE]": False
	}

	for line in buf:
		for key in matches:
			if re.search(key, line):
				matches[key] = True

	if (matches["--------+"] and matches["|"]) or (matches["T[aAbBlLeE]"] and matches["--------+"]):
		return True

	return False


def fatal( errorMsg ):
	logging.critical(errorMsg)
	exit(1)
	return


def loadFile(fn):
	inBuf = []
	encoding = ""

	if not os.path.isfile(fn):
		fatal("File not found: {}".format(fn))

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

def processSidenotes( inBuf, keepOriginal ):
	sidenotesCount = 0
	lineNum = 0
	outBuf = []

	logging.info("--- Processing sidenotes")
	while lineNum < len(inBuf):

		# Search for sidenotes
		if re.match(r"\*?\[Sidenote", inBuf[lineNum]):
			startLine = lineNum

			# Copy sidenote block
			snBlock = []
			snBlock.append(inBuf[lineNum])
			while lineNum < len(inBuf)-1 and not re.search(r"][\*]*$", inBuf[lineNum]):
				lineNum += 1
				snBlock.append(inBuf[lineNum])

			endLine = lineNum

			# Strip markup text from [sidenote] block
			snText = []
			for line in snBlock:
				line = re.sub(r"^\*?\[Sidenote: ?", "", line)
				line = re.sub(r"]$", "", line)
				snText.append(line)

			# Need to relocate *[Sidenote
			if inBuf[startLine][0] == '*':
				outBuf.append("// *** DP2PPGEN: RELOCATE SIDENOTE")

			# Ouput ppgen style sidenote
			s = ".sn {}".format(' '.join(snText))
			outBuf.append(s)
			sidenotesCount += 1
			lineNum += 1

		else:
			outBuf.append(inBuf[lineNum])
			lineNum += 1

	logging.info("--- Processed {} sidenotes".format(sidenotesCount))

	return outBuf;


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
		if isLinePageBreak(inBuf[lineNum]):
			currentScanPage = parseScanPage(inBuf[lineNum])
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

			# Strip markup text from [Footnote] block
			fnText = []
			for line in fnBlock:
				line = re.sub(r"^\*\[Footnote: ?", "", line)
				line = re.sub(r"^\[Footnote [A-Z]: ?", "", line)
				line = re.sub(r"^\[Footnote \d+: ?", "", line)
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
		if isLinePageBreak(outBuf[lineNum]):
			anchorsThisPage = []
			currentScanPage = parseScanPage(inBuf[lineNum])
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
				# replace [1] or [A] with [n]
				curAnchor = "\[{}\]".format(anchor)
				logging.debug("curAnchor={} anchorsThisPage={}".format(curAnchor,anchorsThisPage))
				if not curAnchor in anchorsThisPage:
					fnAnchorCount += 1
					anchorsThisPage.append(curAnchor)

				newAnchor = "[{}]".format(fnAnchorCount)
				#TODO: add option to use ppgen autonumber? [#].. unsure if good reason to do this, would hide footnote mismatch errors and increase ppgen project compile times

				logging.debug("{:>5s}: ({}|{}) ... {} ...".format(newAnchor,lineNum+1,currentScanPageLabel,outBuf[lineNum]))
				for line in footnotes[fnAnchorCount-1]['fnText']:
					logging.debug("       {}".format(line))

				# sanity check (anchor and footnote should be on same scan page)
				if currentScanPage != footnotes[fnAnchorCount-1]['scanPageNum']:
					logging.fatal("Anchor found on different scan page, anchor({}) and footnotes({}) may be out of sync".format(currentScanPage,footnotes[fnAnchorCount-1]['scanPageNum']))
					exit(1)

				# replace anchor
				outBuf[lineNum] = re.sub(curAnchor, newAnchor, outBuf[lineNum])

				# update paragraphEnd and chapterEnd so they are relative to anchor and not [Footnote
				# Find end of paragraph
				paragraphEnd = findNextEmptyLine(outBuf, lineNum)
				footnotes[fnAnchorCount-1]['paragraphEnd'] = paragraphEnd

				# Find end of chapter (line after last line of last paragraph)
				# Chapter headings must be marked in ppgen format (.h2)
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
	logging.info("--- Removing blank lines before [Footnotes]")
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

		fnMarkup.append(".sp 4")
		fnMarkup.append(".pb")
		fnMarkup.append(".de div.footnotes { border: dashed 1px #aaaaaa; padding: 1.5em; }")
		fnMarkup.append(".de div.footnotes h2 { margin-top: 1em; }")
		fnMarkup.append('.dv class="footnotes"')
		fnMarkup.append(".sp 2")
		fnMarkup.append(".h2 id=footnotes nobreak")
		fnMarkup.append("FOOTNOTES:")
		fnMarkup.append(".sp 2")

		for i, fn in enumerate(footnotes):
			fnMarkup.append(".fn {}".format(i+1))
			for line in fn['fnText']:
				fnMarkup.append(line)
			fnMarkup.append(".fn-")

		fnMarkup.append(".dv-")

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

			if ln < len(inBuf) and isLinePageBreak(inBuf[ln]):
				outBlock.append(inBuf[ln])
				ln += 1
				while ln < len(inBuf)-1 and isLineBlank(inBuf[ln]) or re.match(r".pn",inBuf[ln]) or re.match(r"\/\/",inBuf[ln]):
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

		if re.search(r"\-\*$", inBuf[lineNum]) and isLinePageBreak(inBuf[lineNum+1]):
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


def tabsToSpaces( inBuf, tabSize ):
	outBuf = []

	for line in inBuf:
		spaces = " " * tabSize
		line = line.replace("\t", spaces)
		outBuf.append(line)

	return outBuf


def convertUTF8( inBuf ):
	outBuf = []
	lineCount = 0

	logging.info("-- Converting characters to UTF-8")

	for i, line in enumerate(inBuf):
		originalLine = line
		if not isLinePageBreak(line):
			# -- becomes a unicode mdash, ---- becomes 2 unicode mdashes
			line = re.sub(r"(?<!-)-{2}(?!-)","—", line)
			line = re.sub(r"(?<!-)-{4}(?!-)","——", line)
			if "--" in line:
				logging.warn("Unconverted dashes: {}".format(line))

		# [oe] becomes œ
		# [OE] becomes Œ
		line = line.replace("[oe]", "œ")
		line = line.replace("[OE]", "Œ")

		if line != originalLine:
			lineCount += 1
			logging.debug("[{}] {}".format(i,originalLine))
			logging.debug("{}{}".format(" "*(len(str(i))+3),line))

		outBuf.append(line)

		# Fractions?

	logging.info("-- Finished converting characters on {} lines to UTF-8".format(lineCount))
	return outBuf


def convertThoughtBreaks( inBuf ):
	outBuf = []

	for line in inBuf:
		# <tb> to .tb
		line = re.sub(r"^<tb>$",".tb", line)
		outBuf.append(line)

	return outBuf


def removeBlankLinesAtPageEnds( inBuf ):
	outBuf = []

	for line in inBuf:
		if isLinePageBreak(line):
			while outBuf and isLineBlank(outBuf[-1]):
				outBuf.pop()

		outBuf.append(line)

	return outBuf


# TODO: Make this a tool in itself?
def fixup( inBuf, keepOriginal ):
#    • Remove spaces at end of line.
#    • Remove blank lines at end of pages.
#    • Remove spaces on either side of hyphens.
#    • Remove space before periods.
#    • Remove space before exclamation points.
#    • Remove space before question marks.
#    • Remove space before commas.
#    • Remove space before semicolons.
#    • Remove space before colons.
#    • Remove space after opening and before closing brackets. () [] {}
#    • Remove space after open angle quote and before close angle quote.
#    • Remove space after beginning and before ending double quote.
#    • Ensure space before ellipses except after period.
#    • Format any line that contains only 5 *s and whitespace to be the standard 5 asterisk thought break.
#    • Convert multiple space to single space.
#    • Fix obvious l<-->1 problems.
#    You can also specify whether to skip text inside the /* */ markers or not.


	outBuf = inBuf

	outBuf = tabsToSpaces(outBuf, 4)
	outBuf = removeTrailingSpaces(outBuf)
	outBuf = convertThoughtBreaks(outBuf)
	outBuf = removeBlankLinesAtPageEnds(outBuf)
#	outBuf = removeExtraSpaces(outBuf)

	return outBuf

#TODO: Full guiguts fixit seems error prone.. maybe only do safe defaults or break off into seperate tool with each setting configurable, does gutsweeper do this already?
#def removeExtraSpaces( inBuf ):
#    • Remove spaces on either side of hyphens.
#    • Remove space before periods.
#    • Remove space before exclamation points.
#    • Remove space before question marks.
#    • Remove space before commas.
#    • Remove space before semicolons.
#    • Remove space before colons.
#    • Remove space after opening and before closing brackets. () [] {}
#    • Remove space after open angle quote and before close angle quote.
#    • Remove space after beginning and before ending double quote.
#    • Ensure space before ellipses except after period.
#	rewrapLevel = 0
#	for line in inBuf:
#		# Detect when inside out-of-line formatting block /# #/ /* */
#		if re.match(r"^\/[\*\#]", inBuf[lineNum]):
#			rewrapLevel += 1
#		elif re.match(r"^[\*\#]\/", inBuf[lineNum]):
#			rewrapLevel -= 1
#
#		if rewrapLevel == 0:
#			# Remove multiple spaces
#			# $line =~ s/(?<=\S)\s\s+(?=\S)/
#			line = re.sub(r"(?<=\S)\s\s+(?=\S)","", line)
#
#			# Remove spaces on either side of hyphens.
#			# Remove spaces before hyphen (only if hyphen isn't first on line, like poetry)
#			# $line =~ s/(\S) +-/$1-/g;
#			line = re.sub(r"(\S) +-","\1-", line)
#
#			# Remove space after hyphen
#			# $line =~ s/- /-/g;
#			line = re.sub(r"- ","-", line)
#
#			# Except leave a space after a string of three or more hyphens
#			# $line =~ s/(?<![-])([-]*---)(?=[^\s\\"F-])/$1 /g
#			line = re.sub(r'(?<!-)(-*---)(?=[^\s\\"F-])',"\1", line)
#
#		outBuf.append(line)
#
#	return outBuf
#
#				$edited++ if $line =~ s/- /-/g;    # Remove space after hyphen
#				$edited++
#				  if $line =~ s/(?<![-])([-]*---)(?=[^\s\\"F-])/$1 /g
#				; # Except leave a space after a string of three or more hyphens
#
#
#
#			if ( ${ $::lglobal{fixopt} }[1] ) {
#				; # Remove spaces before hyphen (only if hyphen isn't first on line, like poetry)
#				$edited++ if $line =~ s/(\S) +-/$1-/g;
#				$edited++ if $line =~ s/- /-/g;    # Remove space after hyphen
#				$edited++
#				  if $line =~ s/(?<![-])([-]*---)(?=[^\s\\"F-])/$1 /g
#				; # Except leave a space after a string of three or more hyphens
#			}
#			if ( ${ $::lglobal{fixopt} }[3] ) {
#				; # Remove space before periods (only if not first on line, like poetry's ellipses)
#				$edited++ if $line =~ s/(\S) +\.(?=\D)/$1\./g;
#			}
#			;     # Get rid of space before periods
#			if ( ${ $::lglobal{fixopt} }[4] ) {
#				$edited++
#				  if $line =~ s/ +!/!/g;
#			}
#			;     # Get rid of space before exclamation points
#			if ( ${ $::lglobal{fixopt} }[5] ) {
#				$edited++
#				  if $line =~ s/ +\?/\?/g;
#			}
#			;     # Get rid of space before question marks
#			if ( ${ $::lglobal{fixopt} }[6] ) {
#				$edited++
#				  if $line =~ s/ +\;/\;/g;
#			}
#			;     # Get rid of space before semicolons
#			if ( ${ $::lglobal{fixopt} }[7] ) {
#				$edited++
#				  if $line =~ s/ +:/:/g;
#			}
#			;     # Get rid of space before colons
#			if ( ${ $::lglobal{fixopt} }[8] ) {
#				$edited++
#				  if $line =~ s/ +,/,/g;
#			}
#			;     # Get rid of space before commas
#			      # FIXME way to go on managing quotes
#			if ( ${ $::lglobal{fixopt} }[9] ) {
#				$edited++
#				  if $line =~ s/^\" +/\"/
#				; # Remove space after doublequote if it is the first character on a line
#				$edited++
#				  if $line =~ s/ +\"$/\"/
#				; # Remove space before doublequote if it is the last character on a line
#			}
#			if ( ${ $::lglobal{fixopt} }[10] ) {
#				$edited++
#				  if $line =~ s/(?<=(\(|\{|\[)) //g
#				;    # Get rid of space after opening brackets
#				$edited++
#				  if $line =~ s/ (?=(\)|\}|\]))//g
#				;    # Get rid of space before closing brackets
#			}
#			;        # FIXME format to standard thought breaks - changed to <tb>
#			if ( ${ $::lglobal{fixopt} }[11] ) {
#				$edited++
#
#		   #				  if $line =~
#		   # s/^\s*(\*\s*){5}$/       \*       \*       \*       \*       \*\n/;
#				  if $line =~ s/^\s*(\*\s*){4,}$/<tb>\n/;
#			}
#			$edited++ if ( $line =~ s/ +$// );
#			;        # Fix llth, lst
#			if ( ${ $::lglobal{fixopt} }[12] ) {
#				$edited++ if $line =~ s/llth/11th/g;
#				$edited++ if $line =~ s/(?<=\d)lst/1st/g;
#				$edited++ if $line =~ s/(?<=\s)lst/1st/g;
#				$edited++ if $line =~ s/^lst/1st/;
#			}
#			;        # format ellipses correctly
#			if ( ${ $::lglobal{fixopt} }[13] ) {
#				$edited++ if $line =~ s/(?<![\.\!\?])\.{3}(?!\.)/ \.\.\./g;
#				$edited++ if $line =~ s/^ \./\./;
#			}
#			;        # format guillemets correctly
#			;        # french guillemets
#			if ( ${ $::lglobal{fixopt} }[14] and ${ $::lglobal{fixopt} }[15] ) {
#				$edited++ if $line =~ s/«\s+/«/g;
#				$edited++ if $line =~ s/\s+»/»/g;
#			}
#			;        # german guillemets
#			if ( ${ $::lglobal{fixopt} }[14] and !${ $::lglobal{fixopt} }[15] )
#			{
#				$edited++ if $line =~ s/\s+«/«/g;
#				$edited++ if $line =~ s/»\s+/»/g;
#			}
#			$update++ if ( ( $index % 250 ) == 0 );
#			$textwindow->see($index) if ( $edited || $update );
#			if ($edited) {
#				$textwindow->replacewith( $lastindex, $index, $line );
#			}
#		}
#		$textwindow->markSet( 'insert', $index ) if $update;
#		$textwindow->update   if ( $edited || $update );
#		::update_indicators() if ( $edited || $update );
#		$edited    = 0;
#		$update    = 0;
#		$lastindex = $index;
#		$index++;
#		$index .= '.0';
#		if ( $index > $end ) { $index = $end }
#		if ($::operationinterrupt) { $::operationinterrupt = 0; return }
#	}
#	$textwindow->markSet( 'insert', 'end' );
#	$textwindow->see('end');
#	::update_indicators();
#}

def doStandardConversions( inBuf, keepOriginal ):
	outBuf = inBuf

	outBuf = removeTrailingSpaces(outBuf)
	outBuf = convertThoughtBreaks(outBuf)

	return outBuf


def main():
	args = docopt(__doc__, version="dp2ppgen v{}".format(VERSION))

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
	doSidenotes = args['--sidenotes'];
	doTables = args['--tables'];
	doPages = args['--pages'];
	doJoinSpanned = args['--joinspanned'];
	doFixup = args['--fixup'];
	doUTF8 = args['--utf8'];

	#TODO, load config file and use those options if one is present

	# Use default options if no processing options are set
	if not doChapterHeadings and \
		not doSectionHeadings and \
		not doFootnotes and \
		not doSidenotes and \
		not doTables and \
		not doPages and \
		not doFixup and \
		not doUTF8 and \
		not doJoinSpanned:

		logging.info("No processing options were given, using default set of options -pcfj --fixup --utf8\n      Run 'dp2ppgen -h' for a full list of options")
		doPages = True
		doChapterHeadings = True
		doFootnotes = True
		doSidenotes = True
		doFixup = False
		doUTF8 = True
		doJoinSpanned = True

	# Process source document
	logging.info("Processing '{}'".format(infile))
	outBuf = inBuf

	errorCount = validateDpMarkup(inBuf)
	if errorCount > 0 and not args['--force']:
		fatal("Correct markup issues then re-run operation, or use --force to ignore markup errors")

	else:
		outBuf = doStandardConversions(outBuf, args['--keeporiginal'])

		if doPages:
			outBuf = processBlankPages(outBuf, args['--keeporiginal'])
			outBuf = processPageNumbers(outBuf, args['--keeporiginal'])
		if doFixup:
			outBuf = fixup(outBuf, args['--keeporiginal'])
		if doUTF8:
			outBuf = convertUTF8(outBuf)
		if doChapterHeadings or doSectionHeadings:
			outBuf = processHeadings(outBuf, doChapterHeadings, doSectionHeadings, args['--keeporiginal'])
		if doSidenotes:
			outBuf = processSidenotes(outBuf, args['--keeporiginal'])
		if doFootnotes:
			footnoteDestination = "bookend"
			if args['--fndest']:
				footnoteDestination = args['--fndest']
			outBuf = processFootnotes(outBuf, footnoteDestination, args['--keeporiginal'])
		if doJoinSpanned:
			outBuf = joinSpannedFormatting(outBuf, args['--keeporiginal'])
			outBuf = joinSpannedHyphenations(outBuf, args['--keeporiginal'])
		if doTables:
			outBuf = processTables(outBuf, args['--keeporiginal'])

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
