import logging
import datetime
import os.path
logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)
consoleh = logging.StreamHandler()
logger.addHandler(consoleh)


class UnderCloud(object):

    TEMPEST_URL = "https://github.com/openstack/tempest.git"
    TEMPEST_DIR = "/home/stack/tempest_" + (datetime.datetime.today()).isoformat()
    TEMPEST_CONF_FILE = "{0}/tempest/etc/tempest.conf".format(TEMPEST_DIR)
    CWD = os.path.dirname(os.path.realpath(__file__))
    CRUDINI_COMMANDS = []

    def __init__(self):
        self.controller_nodes = list()
        self.compute_nodes = list()

    def source_stackrc(self):
        return "source /home/stack/stackrc"

    def source_overcloudrd(self):
        return "source /home/stack/overcloudrc"

    def run_cloud_cleanup(self, ssh):
        clean_repo = "https://github.com/bkopilov/tempest_cleanup.git"
        ssh.send_cmd("git clone {0}".format(clean_repo))
        ssh.send_cmd("cd tempest_cleanup && ./tempest_cleanup.sh",ignore_exit=True)

    def get_undercloud_nodes(self, ssh):
        nova_list = """nova list | awk '{print $4 " " $12}' | sed  's/=/ /g' """
        cmd = self.source_stackrc() + "&& " + nova_list
        nodes = ssh.send_cmd(cmd)
        for node in nodes:
            node_list = node.split()
            if "ctlplane" in node:
                if "controller" in node:
                    self.controller_nodes.append(node_list[2])
                elif "compute" in node:
                    self.compute_nodes.append(node_list[2])

    def show_overcloud_nodes(self):
        for controller in self.controller_nodes:
            logger.info("Controller: {0}".format(controller))
        for compute in self.compute_nodes:
            logger.info("Compute: {0}".format(compute))

    def prepare_tempest_directory(self, ssh):
        self.prepare_packages_for_tempest(ssh)
        ssh.send_cmd("mkdir {0}".format(self.TEMPEST_DIR))
        tepmest_directory = "cd {0} && ".format(self.TEMPEST_DIR)
        ssh.send_cmd("{0} git clone {1}".format(tepmest_directory, self.TEMPEST_URL))
        ssh.send_cmd("sudo pip install {0}/tempest ".format(self.TEMPEST_DIR))
        ssh.send_cmd("sudo pip install -r {0}/tempest/requirements.txt ".format(self.TEMPEST_DIR))
        ssh.send_cmd("sudo pip install -r  {0}/tempest/test-requirements.txt ".format(self.TEMPEST_DIR))

    def prepare_packages_for_tempest(self, ssh):
        ssh.send_cmd("sudo yum install -y gcc wget libxslt-devel libxml2-devel"
                     " python-devel openssl-devel libffi-devel python-testtools",ignore_exit=True)
        ssh.send_cmd("sudo easy_install pip ",ignore_exit=True)
        ssh.send_cmd("sudo pip install junitxml tox virtualenv", ignore_exit=True)

    def prepare_tempest_roles(self, ssh):
        # role list:
        role_list = """ openstack role list | awk '{print $4}' | grep -v -E "^$|Name" """
        cmd = self.source_overcloudrd() + "&&" + role_list
        current_roles = ssh.send_cmd(cmd)
        needed_roles = ["admin", "_member_", "heat_stack_user", "ResellerAdmin", "swiftoperator","heat_stack_owner"]
        for role_name in needed_roles:
            if role_name not in current_roles:
                ssh.send_cmd(self.source_overcloudrd() + "&&" +
                             "openstack role create {0}".format(role_name))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " auth tempest_roles _member_".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " object-storage operator_role "
                                     "swiftoperator".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " orchestration stack_owner_role heat_stack_owner".format(self.TEMPEST_CONF_FILE))

    def prepare_tempest_debug(self):
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " DEFAULT debug false".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " DEFAULT use_stderr false".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " DEFAULT log_file tempest.log".format(self.TEMPEST_CONF_FILE))

    def prepare_tempest_identity(self, ssh):
        # user-lists:
        user_list = """openstack user list  | awk '{print $4}' | grep -v -E "^$|Name" """
        tenant_list = """openstack project list  | awk '{print $4}' | grep -v -E "^$|Name" """
        current_user_list = ssh.send_cmd(self.source_overcloudrd() + "&&" + user_list)
        current_tenant_list = ssh.send_cmd(self.source_overcloudrd() + "&&" + tenant_list)
        needed_users_tenants = ["demo", "alt_demo"]
        for user in needed_users_tenants:
            if user in current_user_list:
                ssh.send_cmd(self.source_overcloudrd() + "&&" + "openstack user delete {0}".format(user))
        for tenant in needed_users_tenants:
            if tenant in current_tenant_list:
                ssh.send_cmd(self.source_overcloudrd() + "&&" + "openstack project delete {0}".format(tenant))
        # create new project and user
        for user in needed_users_tenants:
            tenant_create = """ openstack project create {0} --description {0} --enable | grep " id " |awk '{{print $4}}' """.format(user)
            tenant_id = ssh.send_cmd(self.source_overcloudrd() + " && " + tenant_create)
            user_create = """openstack user create {0} --project {1} --password secrete --enable""".format(user, tenant_id[0])
            ssh.send_cmd(self.source_overcloudrd() + " && " + user_create)
        # update curdini
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity username demo".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity tenant_name demo".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity password secrete".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity alt_username alt_demo".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity alt_tenant_name alt_demo".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity alt_password secrete".format(self.TEMPEST_CONF_FILE))
        # update admin :
        admin_pass = ssh.send_cmd(self.source_overcloudrd() + " && " + "echo $OS_PASSWORD")
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity admin_username admin".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity admin_tenant_name admin".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity admin_domain_name Default".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity admin_password {1}"
                                     .format(self.TEMPEST_CONF_FILE, admin_pass[0]))
        # uri endpoint and horizon:
        uri_v2 = ssh.send_cmd(self.source_overcloudrd() + " && " + "echo $OS_AUTH_URL")
        uri_v3 = uri_v2[0].split(":5000")[0] + ":5000/v3/"
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity uri {1}".format(self.TEMPEST_CONF_FILE, uri_v2[0]))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity uri_v3 {1}".format(self.TEMPEST_CONF_FILE, uri_v3))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " dashboard dashboard_url {1}".format(self.TEMPEST_CONF_FILE, uri_v2[0].split(":5000")[0] + "/dashboard/"))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " dashboard login_url {1}".format(self.TEMPEST_CONF_FILE, uri_v2[0].split(":5000")[0] + "/dashboard/auth/login/"))

        # admin tenant_id
        admin_tenant_cmd = "openstack project list | grep admin | awk '{{print $2}}'"
        admin_tenant_id = ssh.send_cmd(self.source_overcloudrd() + " && " + admin_tenant_cmd)
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " identity admin_tenant_id {1}".format(self.TEMPEST_CONF_FILE, admin_tenant_id[0]))

    def prepare_tempest_oslo(self):
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " oslo_concurrency lock_path /tmp".format(self.TEMPEST_CONF_FILE))

    def prepare_tempest_services_enable(self):
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " service_available neutron true".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute-feature-enabled resize true".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute-feature-enabled block_migration_for_live_migration true".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute-feature-enabled live_migrate_paused_instances true".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute-feature-enabled vnc_console true".format(self.TEMPEST_CONF_FILE))

    def prepare_tempest_image(self, ssh):
        wget_url = "http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img"
        image_name = wget_url.split("/")[4]
        create_image = "openstack image create {0} " \
                       "--public --container-format=bare " \
                       "--disk-format=qcow2 < {0} | grep id| awk '{{print $4}}'".format(image_name)
        ssh.send_cmd(self.source_overcloudrd() + " && " + "wget " + wget_url)
        image_id = ssh.send_cmd(self.source_overcloudrd() + " && " + create_image)
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute image_ssh_user cirros".format(self.TEMPEST_CONF_FILE))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute image_ref {1}".format(self.TEMPEST_CONF_FILE ,image_id[0]))
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " compute image_ref_alt {1}".format(self.TEMPEST_CONF_FILE, image_id[0]))

    def prepare_tempest_extension(self, ssh):
        # volume_ext
        extention_services = [["--compute", "compute-feature-enabled"],
                              ("--identity", "identity-feature-enabled"),
                              ["--network", "network-feature-enabled"],
                              ["--volume", "volume-feature-enabled"]]

        for extention in extention_services:
            ext = "openstack extension list {0} -c Alias | grep -v -E '\-\-\-|Alias' | awk '{{print $2}}'".format(extention[0])
            ext_list = ssh.send_cmd(self.source_overcloudrd() + " && " + ext)
            ext_str = ",".join(ext_list)
            self.CRUDINI_COMMANDS.append("crudini --format=ini --set $TEMPEST_FILE"
                                         " {0} api_extensions {1}".format(extention[1], ext_str))

    def prepare_tempest_public_net(self, ssh):
        # assume nova is the external network
        public_net = "openstack network list  -c ID -c Name| grep nova | awk '{{ print $2}}'"
        public_network_id = ssh.send_cmd(self.source_overcloudrd() + "&& " + public_net)
        self.CRUDINI_COMMANDS.append("crudini --format=ini --set {0}"
                                     " network public_network_id {1}"
                                     .format(self.TEMPEST_CONF_FILE, public_network_id[0]))

    def prepare_tempest_conf_file(self, ssh):
        for line in self.CRUDINI_COMMANDS:
            ssh.send_cmd(line)

    def run_tempest_tests(self,ssh):
        tempest_directory = self.TEMPEST_DIR + "/tempest"
        testr_init = "cd {0} && testr init".format(tempest_directory)
        ssh.send_cmd(testr_init)
        ssh.send_cmd("cd {0} && testr list-tests | tee  list-tests".format(tempest_directory))
        # download colorizer:
        colorizer = "cd {0} && {1}".format(tempest_directory,
                                           "wget https://raw.githubusercontent.com/openstack/tempest/8843f0f0768019c76be72b4be2f6a156cdbe3d78/tools/colorizer.py")
        ssh.send_cmd(colorizer)
        ssh.send_cmd("cd {0} && sudo chmod 755 colorizer.py".format(tempest_directory))
        run_tempest = "cd {0} && testr run  --load-list={1} " \
                      "--subunit | tee >(subunit2junitxml " \
                      "--output-to=xunit_temp0.xml) | " \
                      "subunit-2to1 | {2} ".format(tempest_directory, tempest_directory + "/list-tests", tempest_directory + "/colorizer.py")
        ssh.send_cmd(run_tempest)




















