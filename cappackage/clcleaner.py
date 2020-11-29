#!/usr/bin/python3
#coding:utf-8
import os, sys

class Stream:
	EOF = (-1)

	def __init__(self, src):
		self._src = src
		self._limit = len(src)
		self._index = 0

	def eof(self):
		return self._index >= self._limit or self._index < 0

	def get(self):
		if self.eof():
			return self.EOF

		ch = self._src[self._index]
		self.next()
		return ch

	def cur(self, ofs=0):
		i = self._index + ofs
		if i < self._limit and i >= 0:
			return self._src[i]
		return self.EOF

	def prev(self):
		if self._index > 0:
			self._index -= 1

	def next(self):
		if self._index < self._limit:
			self._index += 1

class Token():
	UNKNOWN = (0)
	ARG = (100)
	SHORTOPT = (200)
	SHORTOPTASS = (201)
	LONGOPT = (400)
	LONGOPTASS = (401)

	def __init__(self, typ=(0), value=''):
		self._type = typ
		self._value = value

	def __str__(self):
		return '<token type="{0}" value="{1}">'.format(self._type, self._value)

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, value):
		self._value = value

	@value.getter
	def value(self):
		return self._value
	
	@property
	def type(self):
		return self._type

	@type.setter
	def type(self, typ):
		self._type = typ

	@type.getter
	def type(self):
		return self._type
	
##
# cap command arg arg
#
class CommandLineCleaner():
	def __init__(self, **args):
		self.isdebug = args.pop('debug', False)

	def isnormch(self, ch):
		return ch.isalnum() or ch in '-_'

	def isblank(self, ch):
		return ch.isspace() or ch in '\n\t'

	def splitcmd(self, cmd):
		s = Stream(cmd + ' ')
		m = 0
		val = ''
		toks = []

		while not s.eof():
			c = s.get()

			if self.isdebug:
				print(m, c)

			if m == 0:
				if self.isblank(c):
					pass
				elif c == '-':
					m = 100
					val += c
				elif c == '"':
					m = 200
				elif c == "'":
					m = 300
				else:
					m = 400
					val += c
			elif m == 100: # -
				if c == '-':
					m = 150
					val += c
				elif self.isblank(c):
					toks.append(Token(Token.ARG, val))
					val = ''
					m = 0
				else:
					m = 120
					val += c
			elif m == 120: # -?
				if self.isblank(c):
					toks.append(Token(Token.SHORTOPT, val))
					val = ''
					m = 0
				elif c == '=':
					val += c
					m = 140
				else:
					val += c
			elif m == 140: # -?=
				if c == '\\':
					val += c
					val += s.get()
				elif c == '"':
					m = 141
				elif c == "'":
					m = 142
				elif self.isblank(c):
					toks.append(Token(Token.SHORTOPTASS, val))
					val = ''
					m = 0
				else:
					val += c
			elif m == 141: # -?="?"
				if c == '\\':
					val += c
					val += s.get()
				elif c == '"':
					toks.append(Token(Token.SHORTOPTASS, val))
					val = ''
					m = 0
				else:
					val += c
			elif m == 142: # -?='?'
				if c == '\\':
					val += c
					val += s.get()
				elif c == "'":
					toks.append(Token(Token.SHORTOPTASS, val))
					val = ''
					m = 0
				else:
					val += c
			elif m == 150: # --?
				if self.isblank(c):
					toks.append(Token(Token.LONGOPT, val))
					val = ''
					m = 0
				elif c == '=':
					val += c
					m = 160 
				else:
					val += c
			elif m == 160: # --?=
				if c == '\\':
					val += c
					val += s.get()
				elif c == '"':
					m = 161
				elif c == "'":
					m = 162
				elif self.isblank(c):
					toks.append(Token(Token.LONGOPTASS, val))
					val = ''
					m = 0
				else:
					val += c
			elif m == 161: # --?="?"
				if c == '\\':
					val += c
					val += s.get()
				elif c == '"':
					toks.append(Token(Token.LONGOPTASS, val))
					val = ''
					m = 0
				else:
					val += c
			elif m == 162: # --?="?"
				if c == '\\':
					val += c
					val += s.get()
				elif c == "'":
					toks.append(Token(Token.LONGOPTASS, val))
					val = ''
					m = 0
				else:
					val += c
			elif m == 200: # "arg"
				if c == '\\':
					val += c
					val += s.get()
				elif c == '"':
					m = 0
					toks.append(Token(Token.ARG, val))
					val = ''
				else:
					val += c
			elif m == 300: # 'arg'
				if c == '\\':
					val += c
					val += s.get()
				elif c == "'":
					m = 0
					toks.append(Token(Token.ARG, val))
					val = ''
				else:
					val += c
			elif m == 400: # arg
				if c == '\\':
					val += c
					val += s.get()
				elif self.isblank(c):
					m = 0
					toks.append(Token(Token.ARG, val))
					val = ''
				else:
					val += c

		return toks

	def wrapquote(self, tok, quote='"'):
		T = Token
		v = ''

		if tok.type in (T.SHORTOPTASS, T.LONGOPTASS):
			m = 0
			for c in tok.value:
				if m == 0:
					if c == '=':
						m = 10
						v += c
						v += quote
					else:
						v += c
				elif m == 10:
					v += c
			v += quote
		else:
			v += tok.value
		tok.value =	 v
		return tok

	def escapetok(self, tok):
		s = Stream(tok.value)
		dst = ''

		while not s.eof():
			c = s.get()
			if c == '\\':
				dst += c
				dst += s.get()
				continue
			elif c in '!#<>()|&*':
				dst += '\\'
			dst += c

		tok.value = dst
		return tok

	def escapetoks(self, toks):
		dsts = []
		for tok in toks:
			tok = self.wrapquote(tok, '"')
			tok = self.escapetok(tok)
			dsts.append(tok)
		return dsts

	def jointoks(self, sp, toks):
		cmd = ''
		for t in toks:
			cmd += t.value + sp
		return cmd

	def clean(self, cmd):
		toks = self.splitcmd(cmd)
		if self.isdebug:
			for t in toks: print(t)
		toks = self.escapetoks(toks)
		return self.jointoks(' ', toks).rstrip()

class clcleaner():
	cleaner = CommandLineCleaner(debug=False)

	@staticmethod
	def clean(src):
		return clcleaner.cleaner.clean(src)
	
if __name__ == '__main__':
	cleaner = CommandLineCleaner(debug=False)
	while True:
		cmd = sys.stdin.readline()
		if not cmd:
			break
		cmd = cmd.rstrip('\n')
		print('dirty cmd: [{0}]'.format(cmd))
		cmd = cleaner.clean(cmd)
		print('clean cmd: [{0}]'.format(cmd))
