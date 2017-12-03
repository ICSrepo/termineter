#  termineter/cmd.py
#
#  Copyright 2017 Spencer J. McIntyre <SMcIntyre [at] SecureState [dot] net>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import cmd
import logging
import socket
import ssl

class Cmd(cmd.Cmd):
	def __init__(self, stdin=None, stdout=None, **kwargs):
		super(Cmd, self).__init__(stdin=stdin, stdout=stdout, **kwargs)
		if stdin is not None:
			self.use_rawinput = False
		self._hidden_commands = ['EOF']
		self._disabled_commands = []
		self.__package__ = '.'.join(self.__module__.split('.')[:-1])

	def cmdloop(self):
		while True:
			try:
				super(Cmd, self).cmdloop()
				return
			except KeyboardInterrupt:
				self.print_line('')
				self.print_error('Please use the \'exit\' command to quit')
				continue

	def get_names(self):
		commands = super(Cmd, self).get_names()
		for name in self._hidden_commands:
			if 'do_' + name in commands:
				commands.remove('do_' + name)
		for name in self._disabled_commands:
			if 'do_' + name in commands:
				commands.remove('do_' + name)
		return commands

	def emptyline(self):
		# don't do anything on a blank line being passed
		pass

	def help_help(self):  # Get help out of the undocumented section, stupid python
		self.do_help('')

	def precmd(self, line):  # use this to allow using '?' after the command for help
		tmp_line = line.split()
		if not tmp_line:
			return line
		if tmp_line[0] in self._disabled_commands:
			self.default(tmp_line[0])
			return ''
		if len(tmp_line) == 1:
			return line
		if tmp_line[1] == '?':
			self.do_help(tmp_line[0])
			return ''
		return line

	def do_exit(self, args):
		return True

	def do_EOF(self, args):
		"""Exit The Interpreter"""
		self.print_line('')
		return self.do_exit('')

	@classmethod
	def serve(cls, addr, run_once=False, log_level=None, use_ssl=False, ssl_cert=None, init_kwargs=None):
		init_kwargs = init_kwargs or {}
		__package__ = '.'.join(cls.__module__.split('.')[:-1])
		logger = logging.getLogger(__package__ + '.interpreter.server')

		srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		srv_sock.bind(addr)
		logger.debug('listening for connections on: ' + addr[0] + ':' + str(addr[1]))
		srv_sock.listen(1)
		while True:
			try:
				(clt_sock, clt_addr) = srv_sock.accept()
			except KeyboardInterrupt:
				break
			logger.info('received connection from: ' + clt_addr[0] + ':' + str(clt_addr[1]))

			if use_ssl:
				ssl_sock = ssl.wrap_socket(clt_sock, server_side=True, certfile=ssl_cert)
				ins = ssl_sock.makefile('r', 1)
				outs = ssl_sock.makefile('w', 1)
			else:
				ins = clt_sock.makefile('r', 1)
				outs = clt_sock.makefile('w', 1)

			log_stream = logging.StreamHandler(outs)
			if log_level is not None:
				log_stream.setLevel(log_level)
			log_stream.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
			logging.getLogger('').addHandler(log_stream)

			interpreter = cls(stdin=ins, stdout=outs, **init_kwargs)
			try:
				interpreter.cmdloop()
			except socket.error:
				log_stream.close()
				logging.getLogger('').removeHandler(log_stream)
				logger.warning('received a socket error during the main interpreter loop')
				continue
			log_stream.flush()
			log_stream.close()
			logging.getLogger('').removeHandler(log_stream)

			outs.close()
			ins.close()
			clt_sock.shutdown(socket.SHUT_RDWR)
			clt_sock.close()
			del clt_sock
			if run_once:
				break
		srv_sock.shutdown(socket.SHUT_RDWR)
		srv_sock.close()
