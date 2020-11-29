# -*- coding: utf-8 -*-
"""
ST3 plugin for cap

License: MIT
Author: narupo
Since: 2016
"""
import sublime, sublime_plugin
import subprocess
import os, sys
import platform


""" Load cappackage """
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from cappackage.clcleaner import clcleaner


def get_clip():
    """ Get text of clip board """
    return sublime.get_clipboard().encode('utf-8', errors='ignore')


import time

def run_cmd(cmd, detach=False):
    """ Run command with stdin buffer """
    # Clean dirty command
    cmd = clcleaner.clean(cmd)

    if detach:
        os.environ['CAP_RUN_DETACH'] = '1'

    # Open child process for pipe
    p = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if detach:
        return None, None

    # Read stdout and stderr from child process
    stdin_buf = get_clip()
    start = time.time()
    if len(stdin_buf):
        out, err = p.communicate(stdin_buf)
    else:
        out, err = p.communicate()
    print('cap: communication time:', time.time()-start)

    out = out.decode('utf-8', errors='ignore').replace('\r\n', '\n')
    err = err.decode('utf-8', errors='ignore').replace('\r\n', '\n')

    return out, err


class CapOutputCommand(sublime_plugin.TextCommand):
    """
    CapOutputComamnd

     Run cap command on child process and communicate to parent process for write
    to display
    """

    def run(self, edit, cmd):
        """
        Run output command

        @param object edit
        @param str cmd command line of cap
        """
        out, err = run_cmd(cmd)

        if out:
            # Insert to subl's view on cursor position
            befreg = self.view.sel()[0]

            for pos in self.view.sel():
                self.view.insert(edit, pos.begin(), out)

            # Undo cursor postion
            # TODO: need setting value
            if False:
                self.view.sel().clear()
                self.view.sel().add(befreg)

        if err:
            print(err, file=sys.stderr)


class CapOutputPanelCommand(sublime_plugin.TextCommand):
    """
    CapOutputPanelCommand

     Open output panel, and run command and that result output into panel
    """

    def run(self, edit, cmd, detach=False):
        """ Run command and output into output panel """
        out, err = run_cmd(cmd, detach=detach)
        text = ''
        if out: text = out
        if err: text = err
        if not len(text): return
        sublime.set_clipboard(out)
        window = self.view.window()
        output_view = window.create_output_panel('ResultWindow')
        window.run_command('show_panel', {'panel': 'output.ResultWindow'})
        output_view.set_read_only(False)
        output_view.insert(edit, output_view.size(), text)
        output_view.set_read_only(True)


class CapDetachCommandLineCommand(sublime_plugin.WindowCommand):
    """
    CapDetachCommandLineCommand

     Open input panel on editor and execute & detach input command with CapOutputCommand
    """

    def run(self):
        """ Run command line command """
        self.window.show_input_panel('(detach) cap ', '', self.on_done, None, None)

    def on_done(self, cmd):
        """
        Handle for done of command

        @param str cmd command line of cap
        """
        self.window.run_command('cap_output_panel', {
            'cmd': 'cap ' + cmd,
            'detach': True,
        })


class CapCommandLineCommand(sublime_plugin.WindowCommand):
    """
    CapCommandLineCommand

     Open input panel on editor and execute input command with CapOutputCommand
    """

    def run(self):
        """ Run command line command """
        self.window.show_input_panel('cap ', '', self.on_done, None, None)

    def on_done(self, cmd):
        """
        Handle for done of command

        @param str cmd command line of cap
        """
        self.window.run_command('cap_output_panel', {'cmd': 'cap ' + cmd})


class CapTextLineCommand(sublime_plugin.TextCommand):
    """
    CapTextLineCommand

     Parse cap command on current cursor line and execute it with CapOutputCommand

    Example:

        @cat doc/docker

        or

        @cap cat doc/docker
    """

    def parsetextline(self, edit):
        """
        Parse text of current cursor line then parse and execute command line

        @param object edit
        """
        v = self.view

        sel = v.sel()
        curreg = sel[0]
        linereg = v.line(curreg)

        # Result variables
        cmd = None
        beg = linereg.a
        end = beg

        # Parse text-line-command
        m = 0
        while end < v.size():
            c = v.substr(end)
            end += 1

            if m == 0:
                if c in '@':
                    m = 10
                    beg = end-1
                    cmd = ''
                elif c in '\n':
                    break
            elif m == 10: # Found @
                if c in '\n':
                    break
                elif c in '"':
                    m = 20
                    cmd += c
                elif c in "'":
                    m = 30
                    cmd += c
                else:
                    cmd += c
            elif m == 20: # Found "
                if c in '"':
                    cmd += c
                    m = 10
                elif c in '\n':
                    cmd += ' '
                else:
                    cmd += c
            elif m == 30: # Found '
                if c in "'":
                    cmd += c
                    m = 10
                elif c in '\n':
                    cmd += ' '
                else:
                    cmd += c

        if cmd and cmd[0:4] != 'cap ':
            cmd = 'cap ' + cmd

        if cmd:
            v.erase(edit, sublime.Region(beg, end))

        return cmd

    def run(self, edit):
        """
        Run text line command

        @param object edit
        """
        cmd = self.parsetextline(edit)
        if cmd is None or not len(cmd):
            print('cap on subl3: Error: Invalid text line.', file=sys.stderr)
            return

        # Run command
        self.view.run_command('cap_output', {
            'cmd': cmd,
        })


class CapAutoCompleteCommand(sublime_plugin.EventListener):
    """ Auto complete """

    def on_query_completions(self, view, prefix, locations):
        p = subprocess.Popen(
            'cap alias -g && cap alias',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        out, err = p.communicate()
        if err and len(err):
            print(err, file=sys.stderr)
            return None

        out = out.decode('utf-8').replace('\r\n', '\n').split('\n')
        alsets = []
        for line in out:
            els = [el for el in line.split(' ') if len(el)]
            if len(els) < 2:
                continue
            alname = els[0]
            if alname[0] != prefix:
                continue
            alval = ' '.join([el for el in els[1:]])
            alsets.append((alname, alval))

        matches = []
        for s in alsets:
            trigger = '@{0}  (cap {1})'.format(s[0], s[1])
            content = str(s[0])
            matches.append((trigger, content))

        return matches
