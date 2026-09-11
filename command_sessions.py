"""Owned shell jobs with incremental, bounded output and explicit cancellation."""
from __future__ import annotations
import atexit
import codecs
import os
import signal
import subprocess
import threading
import time
import uuid
from security import minimal_environment, sandbox_argv, git_identity_config


class Buffer:
    def __init__(self, capacity=262144):
        self.text, self.end, self.capacity = '', 0, capacity
        self.lock = threading.Lock()

    def append(self, text):
        with self.lock:
            self.end += len(text)
            self.text = (self.text + text)[-self.capacity:]

    def read(self, offset=0, limit=64000):
        with self.lock:
            oldest = self.end - len(self.text)
            start = min(self.end, max(oldest, offset))
            value = self.text[start-oldest:start-oldest+limit]
            return value, start+len(value), offset < oldest


class Job:
    def __init__(self, process, timeout, cwd, history=None, receipt=None):
        self.process, self.cwd = process, str(cwd)
        self.history, self.receipt = history, receipt or {'status': 'disabled'}
        self.stdout, self.stderr = Buffer(), Buffer()
        self.done = threading.Event()
        self.signal_lock = threading.Lock()
        self.timed_out = False
        self.started = time.time()
        self.readers = []
        for pipe, output in ((process.stdout,self.stdout),(process.stderr,self.stderr)):
            t=threading.Thread(target=self._drain,args=(pipe,output),daemon=True)
            t.start(); self.readers.append(t)
        threading.Thread(target=self._wait,args=(timeout,),daemon=True).start()

    @staticmethod
    def _drain(pipe, output):
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        try:
            while True:
                chunk = os.read(pipe.fileno(), 8192)
                if not chunk: break
                output.append(decoder.decode(chunk))
            output.append(decoder.decode(b'', final=True))
        finally:
            pipe.close()

    def _signal(self, sig):
        with self.signal_lock:
            # The shell may already have exited while its children still own the
            # pipes. The process group remains ours until job cleanup finishes.
            if not self.done.is_set():
                try: os.killpg(self.process.pid, sig)
                except ProcessLookupError: pass

    def stop(self):
        self._signal(signal.SIGTERM)
        if not self.done.wait(1):
            self._signal(signal.SIGKILL)
        self.done.wait(2)

    def _wait(self, timeout):
        try:
            self.process.wait(timeout=timeout or None)
        except subprocess.TimeoutExpired:
            self.timed_out = True
            self._signal(signal.SIGTERM)
            try: self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._signal(signal.SIGKILL)
                self.process.wait()
        finally:
            # Background descendants must not outlive an owned shell job. Send
            # TERM even if the leader exited, then KILL any group still alive.
            self._signal(signal.SIGTERM)
            for thread in self.readers: thread.join(timeout=.5)
            self._signal(signal.SIGKILL)
            for thread in self.readers: thread.join(timeout=2)
            if self.history is not None:
                self.history.finish(self.cwd, self.receipt, self.process.poll(), self.timed_out)
            self.done.set()

    def read(self, out_offset=0, err_offset=0, limit=64000):
        out, out_cursor, out_lost = self.stdout.read(out_offset, limit)
        err, err_cursor, err_lost = self.stderr.read(err_offset, limit)
        return {'running':not self.done.is_set(), 'returncode':self.process.poll(),
                'stdout':out,'stderr':err,'stdout_offset':out_cursor,'stderr_offset':err_cursor,
                'output_truncated':out_lost or err_lost, 'timed_out':self.timed_out,
                'cwd':self.cwd,'started_at':self.started, 'history': dict(self.receipt)}


class CommandSessions:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.RLock()

    def start(self, workspace, cwd, config, command, timeout=0, history=None):
        with self.lock:
            if len(self.jobs) >= 64:
                for key, job in list(self.jobs.items()):
                    if job.done.is_set(): del self.jobs[key]
            if len(self.jobs) >= 64:
                raise ValueError('64 shell jobs are still running; stop one before starting another')
            env = minimal_environment()
            env['PATH']='/home/user/.hermes/node/bin:/usr/local/bin:/usr/bin:/bin'
            fd=os.memfd_create('bridge-job-git',os.MFD_CLOEXEC)
            try:
                os.write(fd,git_identity_config(cwd,env));os.lseek(fd,0,os.SEEK_SET)
                argv=sandbox_argv(workspace,cwd,config,['/bin/bash','--noprofile','--norc','-c',command],git_config_fd=fd)
                receipt = history.begin(str(cwd)) if history is not None else None
                try:
                    process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE,env=env,pass_fds=(fd,),start_new_session=True)
                except Exception:
                    if history is not None:
                        history.finish(str(cwd), receipt, None, unknown=True)
                    raise
            finally:
                os.close(fd)
            key=uuid.uuid4().hex
            self.jobs[key]=Job(process,timeout,cwd,history,receipt)
            return key

    def get(self, key):
        with self.lock:
            if key not in self.jobs:
                raise ValueError('Unknown command session; sessions belong to this Bridge process')
            return self.jobs[key]

    def list(self):
        with self.lock:
            return [{'session_id':k,'running':not j.done.is_set(),'returncode':j.process.poll(),
                     'cwd':j.cwd,'started_at':j.started} for k,j in self.jobs.items()]

    def close(self):
        with self.lock: jobs=list(self.jobs.values())
        for job in jobs:
            if not job.done.is_set():job.stop()


sessions=CommandSessions()
atexit.register(sessions.close)
