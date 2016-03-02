import json
import logging
import datetime
import os.path

logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)
consoleh = logging.StreamHandler()
logger.addHandler(consoleh)


def load_json_file(file_path):
    json_date = open(file_path).read()
    data = json.loads(json_date)
    return data


class UnderCloud(object):
    def __init__(self, config=None):
        self.config = config
        self.nodes = list()
        self.TEMPEST_URL = config["TEMPEST"]["GIT_REPO"]
        self.TEMPEST_DIR = "{0}/tempest_".format(config["TEMPEST"]["WORKING_DIRECTORY"]) \
                           + (datetime.datetime.today()).isoformat()
        self.TEMPEST_CONF_FILE = "{0}/tempest/etc/tempest.conf".format(self.TEMPEST_DIR)
        self.COMMANDS = []
        self.crudini_set = self.config["CRUDINI"] + self.TEMPEST_CONF_FILE

    def source_stackrc(self):
        return "source {0}".format(self.config["UNDERCLOUD"]["STACKRC"])

    def source_overcloudrc(self):
        return "source {0}".format(self.config["UNDERCLOUD"]["OVERCLOUDRC"])

    def run_cloud_cleanup(self, ssh):
        clean_repo = self.config["CLEANUP_CLOUD"]["GIT_REPO"]
        ssh.send_cmd("rm -rf {0}".format(self.config["CLEANUP_CLOUD"]["DIRECTORY_NAME"]))
        ssh.send_cmd("git clone {0}".format(clean_repo))
        ssh.send_cmd("cd {0} && ./tempest_cleanup.sh"
                     .format(self.config["CLEANUP_CLOUD"]["DIRECTORY_NAME"]),
                     ignore_exit=True)

    def get_undercloud_nodes(self, ssh):
        nova_list = """nova list | awk '{print $4 " " $12}' | sed  's/=/ /g' """
        cmd = self.source_stackrc() + "&& " + nova_list
        nodes = ssh.send_cmd(cmd)
        for node in nodes:
            node_list = node.split()
            if "ctlplane" in node:
                self.nodes.append([node_list[0], node_list[2]])

    def get_overcloud_status(self, ssh):
        cmd = self.source_overcloudrc() + "&&" + "openstack-status"
        ssh.send_cmd(cmd)

    def show_overcloud_nodes(self):
        for node in self.nodes:
            logger.info("Node: {0}".format(node))

    def _prepare_tempest_directory(self, ssh):
        self._prepare_packages_for_tempest(ssh)
        ssh.send_cmd("mkdir {0}".format(self.TEMPEST_DIR))
        tepmest_directory = "cd {0} && ".format(self.TEMPEST_DIR)
        ssh.send_cmd("{0} git clone {1}".format(tepmest_directory, self.TEMPEST_URL))
        ssh.send_cmd("sudo pip install {0}/tempest ".format(self.TEMPEST_DIR))
        ssh.send_cmd("sudo pip install -r {0}/tempest/requirements.txt ".format(self.TEMPEST_DIR))
        ssh.send_cmd("sudo pip install -r  {0}/tempest/test-requirements.txt ".format(self.TEMPEST_DIR))

    def _prepare_packages_for_tempest(self, ssh):
        ssh.send_cmd("sudo yum install -y {0}"
                     .format(self.config["TEMPEST"]["YUM_INSTALL"]),
                     ignore_exit=True)
        ssh.send_cmd("sudo easy_install pip ", ignore_exit=True)
        ssh.send_cmd("sudo pip install --upgrade {0} "
                     .format(self.config["TEMPEST"]["PIP_INSTALL"]),
                     ignore_exit=True)

    def _prepare_tempest_roles(self, ssh):
        # role list:
        role_list = """ openstack role list | awk '{print $4}' | grep -v -E "^$|Name" """
        cmd = self.source_overcloudrc() + "&&" + role_list
        current_roles = ssh.send_cmd(cmd)
        needed_roles = ["admin", "_member_", "heat_stack_user", "ResellerAdmin", "swiftoperator", "heat_stack_owner"]
        for role_name in needed_roles:
            if role_name not in current_roles:
                ssh.send_cmd(self.source_overcloudrc() + "&&" +
                             "openstack role create {0}".format(role_name))
        self.COMMANDS.append("{0} auth tempest_roles _member_"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} object-storage operator_role"
                             " swiftoperator".format(self.crudini_set))
        self.COMMANDS.append("{0} orchestration stack_owner_role "
                             "heat_stack_owner".format(self.crudini_set))

    def _prepare_tempest_debug(self):
        self.COMMANDS.append("{0} DEFAULT debug false"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} DEFAULT use_stderr false"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} DEFAULT log_file tempest.log"
                             .format(self.crudini_set))

    def _prepare_tempest_identity(self, ssh):
        # user-lists:
        user_list = """openstack user list  | awk '{print $4}' | grep -v -E "^$|Name" """
        tenant_list = """openstack project list  | awk '{print $4}' | grep -v -E "^$|Name" """
        current_user_list = ssh.send_cmd(self.source_overcloudrc() + "&&" + user_list)
        current_tenant_list = ssh.send_cmd(self.source_overcloudrc() + "&&" + tenant_list)
        needed_users_tenants = ["demo", "alt_demo"]
        for user in needed_users_tenants:
            if user in current_user_list:
                ssh.send_cmd(self.source_overcloudrc() + "&&" + "openstack user delete {0}".format(user))
        for tenant in needed_users_tenants:
            if tenant in current_tenant_list:
                ssh.send_cmd(self.source_overcloudrc() + "&&" + "openstack project delete {0}".format(tenant))
        # create new project and user
        for user in needed_users_tenants:
            tenant_create = "openstack project create {0} --description {0}" \
                            " --enable | grep ' id ' |awk '{{print $4}}'" \
                .format(user)
            tenant_id = ssh.send_cmd(self.source_overcloudrc() + " && "
                                     + tenant_create)
            user_create = "openstack user create {0} --project {1}" \
                          " --password secrete --enable" \
                .format(user, tenant_id[0])
            ssh.send_cmd(self.source_overcloudrc() + " && " + user_create)
        # update curdini
        self.COMMANDS.append("{0} identity username demo"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity tenant_name demo"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity password secrete"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity alt_username alt_demo"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity alt_tenant_name alt_demo"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity alt_password secrete"
                             .format(self.crudini_set))
        # update admin :
        admin_pass = ssh.send_cmd(self.source_overcloudrc() + " && " +
                                  "echo $OS_PASSWORD")
        self.COMMANDS.append("{0} identity admin_username admin"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity admin_tenant_name admin"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity admin_domain_name Default"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} identity admin_password {1}"
                             .format(self.crudini_set, admin_pass[0]))
        # uri endpoint and horizon:
        uri_v2 = ssh.send_cmd(self.source_overcloudrc() + " && " +
                              "echo $OS_AUTH_URL")
        uri_v3 = uri_v2[0].split(":5000")[0] + ":5000/v3/"
        self.COMMANDS.append("{0} identity uri {1}".format(self.crudini_set, uri_v2[0]))
        self.COMMANDS.append("{0} identity uri_v3 {1}".format(self.crudini_set, uri_v3))
        self.COMMANDS.append("{0} dashboard dashboard_url {1}"
                             .format(self.crudini_set,
                                     uri_v2[0].split(":5000")[0] +
                                     "/dashboard/"))
        self.COMMANDS.append("{0} dashboard login_url {1}"
                             .format(self.crudini_set,
                                     uri_v2[0].split(":5000")[0] +
                                     "/dashboard/auth/login/"))

        # admin tenant_id
        admin_tenant_cmd = "openstack project list | grep admin | awk '{{print $2}}'"
        admin_tenant_id = ssh.send_cmd(self.source_overcloudrc() + " && " + admin_tenant_cmd)
        self.COMMANDS.append("{0} identity admin_tenant_id {1}"
                             .format(self.crudini_set, admin_tenant_id[0]))

    def _prepare_tempest_oslo(self):
        self.COMMANDS.append("{0} oslo_concurrency lock_path /tmp"
                             .format(self.crudini_set))

    def _prepare_tempest_services_enable(self):
        self.COMMANDS.append("{0} service_available neutron true".format(self.crudini_set))
        self.COMMANDS.append("{0} compute-feature-enabled resize true".format(self.crudini_set))
        self.COMMANDS.append("{0} compute-feature-enabled"
                             " block_migration_for_live_migration true"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} compute-feature-enabled"
                             " live_migrate_paused_instances true"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} compute-feature-enabled vnc_console true"
                             .format(self.crudini_set))

    def _prepare_tempest_image(self, ssh):
        image_url = self.config["TEMPEST"]["IMAGE_URL"]
        image_name = image_url.split("/")[4]
        create_image = "openstack image create {0} " \
                       "--public --container-format=bare " \
                       "--disk-format=qcow2 < {0} | grep id| awk '{{print $4}}'".format(image_name)
        ssh.send_cmd(self.source_overcloudrc() + " && " + "wget " + image_url)
        image_id = ssh.send_cmd(self.source_overcloudrc() + " && " + create_image)
        self.COMMANDS.append("{0} compute image_ssh_user cirros"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} compute image_ref {1}"
                             .format(self.crudini_set, image_id[0]))
        self.COMMANDS.append("{0} compute image_ref_alt {1}"
                             .format(self.crudini_set, image_id[0]))

    def _prepare_tempest_storage(self):
        self.COMMANDS.append("{0} volume-feature-enabled backup false"
                             .format(self.crudini_set))
        self.COMMANDS.append("{0} volume storage_protocol ceph"
                             .format(self.crudini_set))


    def _prepare_tempest_extension(self, ssh):
        # volume_ext
        extention_services = [["--compute", "compute-feature-enabled"],
                              ("--identity", "identity-feature-enabled"),
                              ["--network", "network-feature-enabled"],
                              ["--volume", "volume-feature-enabled"]]

        for extention in extention_services:
            ext = "openstack extension list {0} -c Alias | grep -v -E '\-\-\-|Alias' | awk '{{print $2}}'".format(
                extention[0])
            ext_list = ssh.send_cmd(self.source_overcloudrc() + " && " + ext)
            ext_str = ",".join(ext_list)
            self.COMMANDS.append("{0} {1} api_extensions {2}"
                                 .format(self.crudini_set, extention[1],
                                         ext_str))

    def _prepare_tempest_public_net(self, ssh):
        # assume nova is the external network
        public_net = "openstack network list  -c ID -c Name| grep public | awk '{{ print $2}}'"
        public_network_id = ssh.send_cmd(self.source_overcloudrc() + "&& " + public_net)
        self.COMMANDS.append("{0} network public_network_id {1}"
                             .format(self.crudini_set, public_network_id[0]))

    def _prepare_tempest_conf_file(self, ssh):
        for line in self.COMMANDS:
            ssh.send_cmd(line)

    def _add_neutron_public_network(self, ssh):
        net_add = "neutron net-create public --router:external" \
                  " --provider:network_type {0} " \
                  "--provider:physical_network {1} --provider:segmentation_id {2}"\
            .format(self.config["EXT_NET"]["NET_TYPE"],
                    self.config["EXT_NET"]["PROVIDER"],
                    self.config["EXT_NET"]["SEGMENT"])
        subnet_add = "neutron subnet-create public {0} " \
                     "--allocation-pool start={1},end={2}" \
                     " --gateway {3}".format(
            self.config["EXT_NET"]["EXTERNAL_SUBNET"],
            self.config["EXT_NET"]["START_POOL"],
            self.config["EXT_NET"]["END_POOL"],
            self.config["EXT_NET"]["GATEWAY"])
        ssh.send_cmd(self.source_overcloudrc() + " && " + net_add)
        ssh.send_cmd(self.source_overcloudrc() + " && " + subnet_add)

    def _run_tempest_tests(self, ssh):
        tempest_directory = self.TEMPEST_DIR + "/tempest"
        testr_init = "cd {0} && testr init".format(tempest_directory)
        ssh.send_cmd(testr_init)
        filter_tests = self.config["TEMPEST"]["FILTER_TESTS"]
        ssh.send_cmd("cd {0} && testr list-tests | {1} | tee  list-tests"
                     .format(tempest_directory, filter_tests))
        # download colorizer:
        colorizer = "cd {0} &&  wget" \
                    " {1}".format(tempest_directory,
                                  self.config["TEMPEST"]["COLORIZED"])
        ssh.send_cmd(colorizer)
        ssh.send_cmd("cd {0} && sudo chmod 755 colorizer.py".format(tempest_directory))
        run_tempest = "cd {0} && testr run  --load-list={1} " \
                      "--subunit | tee >(subunit2junitxml " \
                      "--output-to=xunit_temp.xml) | " \
                      "subunit-2to1 | {2} ".format(tempest_directory, tempest_directory + "/list-tests",
                                                   tempest_directory + "/colorizer.py")
        ssh.send_cmd(run_tempest, timeout=9600, ignore_exit=True)

    def prepare_and_run_tempest_upstream(self, ssh, local_dest_dir):
        self._prepare_tempest_directory(ssh)
        self._prepare_tempest_roles(ssh)
        self._prepare_tempest_identity(ssh)
        self._prepare_tempest_oslo()
        self._prepare_tempest_debug()
        self._prepare_tempest_services_enable()
        self._prepare_tempest_image(ssh)
        self._prepare_tempest_storage()
        self._prepare_tempest_extension(ssh)
        self._add_neutron_public_network(ssh)
        self._prepare_tempest_public_net(ssh)
        self._prepare_tempest_conf_file(ssh)
        self._run_tempest_tests(ssh)
        self._collect_testr_tests(ssh, local_dest_dir)

    def _collect_testr_tests(self, ssh, local_dest_dir):
        ssh_conn = ssh.get_connection()
        sftp = ssh_conn.open_sftp()
        remote_xunit_file = os.path.join(self.TEMPEST_DIR + "/tempest", "xunit_temp.xml")
        local_xunit_file = os.path.join(local_dest_dir, "xunit_temp.xml")
        sftp.get(remote_xunit_file, local_xunit_file)
        sftp.close()

    @staticmethod
    def copy_to_workspace(ssh, local_dest_dir, local_file, remote_file):
        ssh_conn = ssh.get_connection()
        sftp = ssh_conn.open_sftp()
        remote_xunit_file = os.path.join(remote_file)
        local_xunit_file = os.path.join(local_dest_dir, local_file)
        sftp.get(remote_xunit_file, local_xunit_file)
        sftp.close()

    @staticmethod
    def copy_from_workspace(ssh, local_dest_dir, local_file, remote_file,
                            chown=None):
        ssh_conn = ssh.get_connection()
        sftp = ssh_conn.open_sftp()
        remote_file = os.path.join(remote_file)
        local_file = os.path.join(local_dest_dir, local_file)
        ssh.send_cmd("sudo rm -rf {0}".format(remote_file),ignore_exit=True)
        sftp.put(local_file, remote_file)
        if chown:
            ssh.send_cmd("sudo chown {0} {1}".format(chown, remote_file))
            ssh.send_cmd("sudo chmod 777 {0}".format(remote_file))
        sftp.close()

    @staticmethod
    def compress_logs(ssh, log_name, chown=None):
        logs_line = "sudo tar --warning=no-file-changed -czf %s /var/log /etc" % log_name
        ssh.send_cmd(logs_line, ignore_exit=True)
        if chown:
            ssh.send_cmd("sudo chown {0} {1}".format(chown, log_name))
            ssh.send_cmd("sudo chmod 777 {0}".format(log_name))


