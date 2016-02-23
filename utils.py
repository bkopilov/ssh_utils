import inspect
import logging
import os
import select
import signal
import time

import paramiko

POLLING_INTERVAL = 90
SSH_READ_BUFF = 1024
CWD = os.path.dirname(os.path.realpath(__file__))
WORKSPACE = CWD + "/../../"
JOB_NAME = "SSH_UTILS"
logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)
consoleh = logging.StreamHandler()
logger.addHandler(consoleh)


def whoami():
    return inspect.stack()[1][3]


def whosdaddy():
    caller_func = inspect.stack()[2][3]
    if caller_func and "<module>" not in caller_func:
        return caller_func
    else:
        return "main"


class SSH(object):
    def __init__(self, ip, key_file=None, send_password=False,
                 local_dest_dir=WORKSPACE, job_name=JOB_NAME, the_user="root",
                 the_password="qum5net", ssh_attempts=10, port=22):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.ipv4 = str(ip).strip()
        self.port = port
        if self.ipv4 == '':
            # raise error when empty address
            raise RuntimeError("Please configure ipv4 address for ssh")
        self.local_dest_dir = local_dest_dir
        self.job_name = job_name
        self.str_list = []
        dict_args = locals().items()
        for attempt in range(1, ssh_attempts + 1):
            logger.info("SSH attemp to {0}| retry:{1}| args:{2}"
                        .format(ip,
                                attempt,
                                dict_args))
            try:
                if send_password is False:
                    self.client.set_missing_host_key_policy(
                        paramiko.AutoAddPolicy())
                    self.client.connect(hostname=self.ipv4,
                                        username=the_user,
                                        key_filename=key_file,
                                        timeout=30,
                                        look_for_keys=False, port=port)
                    logger.info("Logged in to:%s user:%s "
                                % (self.ipv4, the_user))
                    break
                elif send_password is True:
                    self.client.set_missing_host_key_policy(
                        paramiko.AutoAddPolicy())
                    self.client.connect(hostname=self.ipv4,
                                        username=the_user,
                                        password=the_password, port=port)
                    logger.info("Logged in to: %s user: %s" %
                                (self.ipv4, the_user))
                    break
            except Exception as e:
                logger.info(e)
                time.sleep(POLLING_INTERVAL)
        else:
            raise RuntimeError("### !!! unable to SSH after %s attempts ###" %
                               ssh_attempts)

    def get_connection(self):
        return self.client

    def close_connection(self):
        self.client.close()

    def collect_logs_when_run_fails(self, local_dest_dir=None, job_name=None):
        if local_dest_dir is not None and job_name is not None:
            log_name = "log_" + job_name + ".tar.gz"
            logger.warning("### LOG NAME: %s ###" % log_name)
            if "tempest" in job_name:
                log_line = "sudo tar --warning=no-file-changed" \
                           " --ignore-failed-read -czf /var/%s /opt/tempest "\
                           % log_name
                self.send_cmd(log_line, ignore_exit=True)
            else:
                log_line = "sudo tar --warning=no-file-changed" \
                           " --ignore-failed-read -czf /var/%s " \
                           "/var/log /var/tmp /etc" % log_name
                self.send_cmd(log_line, ignore_exit=True)
            ssh_conn = self.get_connection()
            sftp = ssh_conn.open_sftp()
            archive_file = os.path.join(local_dest_dir, log_name)
            logger.warning("### ARCHIVE_FILE LOGS: %s ###" % archive_file)
            sftp.get("/var/" + log_name, archive_file)
            sftp.close()
        else:
            logger.error("### directory or job_name are none ###")

    def send_cmd(self, cmd, ignore_exit=False, timeout=3600,
                 return_on_timeout=False, timeout_retries=5, prompt_str=None):
        self.str_list = list()
        timeout_exec_counter = 0
        transport = self.client.get_transport()
        channel = transport.open_session()
        channel.get_pty()
        logger.info("[{0}]".format(whosdaddy()))
        logger.info("{0}:{1}|{2}|{3}".format(self.ipv4, self.port, ">>", cmd))
        # redirect al to stdout
        channel.exec_command(cmd + " 2>&1")
        while not channel.exit_status_ready():
            t0 = time.time()  # start time
            select.select([channel], [], [], timeout)
            total_wait_time = int(time.time() - t0)
            if total_wait_time >= timeout:
                timeout_exec_counter += 1
                if return_on_timeout is False:
                    logger.info("### TIMEOUT %s SECONDS - CONTINUE CMD:%s ###"
                                % (total_wait_time, cmd))
                if return_on_timeout is False\
                        and timeout_exec_counter >= timeout_retries:
                    logger.info("### TIMEOUT %s SECONDS - LIMIT  CMD:%s ###" %
                                (total_wait_time, cmd))
                    self.collect_logs_when_run_fails(self.local_dest_dir,
                                                     self.job_name)
                    raise RuntimeError("###TIMEOUT -  EXCEED TIMEOUT RETRY###")
                if return_on_timeout:
                    logger.info("### TIMEOUT AFTER %s SECONDS-CMD:%s ###"
                                % (total_wait_time, cmd))
                    return self.str_list
            while channel.recv_stderr_ready() or channel.recv_ready():
                str_ready = (channel.recv(SSH_READ_BUFF))
                self.str_list.append(str_ready)
                for line in str_ready.splitlines():
                    line = line.strip('\n')
                    logger.info("%s|%s" % ("<<", line))
                    if prompt_str and prompt_str in line:
                        logger.info("prompt: %s found" % prompt_str)
                        return self.str_list
        if not ignore_exit and channel.recv_exit_status() != 0:
            self.collect_logs_when_run_fails(self.local_dest_dir,
                                             self.job_name)
            logger.info("### FAILED - CMD:%s ###" % cmd)
            raise RuntimeError("###COMMAND ERROR: %s ###" % cmd)
        return self.str_list

    def sftp_put(self, local_file, remote_file):
        ssh_conn = self.client
        sftp = ssh_conn.open_sftp()
        logger.info("%s>>>PUT: LOCAL: %s REMOTE: %s" % (self.ipv4, local_file,
                                                        remote_file))
        sftp.put(local_file, remote_file)
        sftp.close()

    def sftp_get(self, remote_file, local_file):
        ssh_conn = self.client
        sftp = ssh_conn.open_sftp()
        logger.info("%s<<<GET: REMOTE: %s LOCAL: %s" % (self.ipv4, remote_file,
                                                        local_file))
        sftp.get(remote_file, local_file)
        sftp.close()

    def _handle_signal_ssh(self, signum, frame):
        raise SystemExit("!!! signal %s received" % signum)

    def __enter__(self):
        logger.info("ssh __enter__ ")
        signal.signal(signal.SIGTERM, self._handle_signal_ssh)
        return self

    def __exit__(self, type, value, traceback):
        logger.info("ssh __exit__%s %s " % (self.ipv4, self.port))
        try:
            self.client.close()
        except Exception:
            logger.info("unable to close ssh connection")
