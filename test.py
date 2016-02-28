import base64
import utils
import common
import os
if __name__ == "__main__":
    CWD = os.path.dirname(os.path.realpath(__file__))
    config = common.load_json_file(CWD + "/config.json")
    """ the password / ipv4 encrypted base64.b64encode("PASS")
        import base64
        print base64.b64encode()
        print base64.b64decode("cGFzc3dvcmQ=")
    """

    with utils.SSH(base64.b64decode(config["SSH"]['IP_ADDRESS']),
                   the_user=base64.b64decode(config["SSH"]['THE_USER']),
                   the_password=base64.b64decode(config["SSH"]['THE_PASSWORD'])
                   ) as ssh:
        cloud = common.UnderCloud(config=config)
        # copy private key to workspace
        cloud.copy_to_workspace(ssh, local_dest_dir=CWD, local_file="id_rsa.tar.gz",
                                remote_file="/home/stack/.ssh/id_rsa")
        #cloud.run_cloud_cleanup(ssh)
        cloud.get_undercloud_nodes(ssh)
        cloud.show_overcloud_nodes()
        cloud.copy_from_workspace(ssh, local_dest_dir=CWD,
                                  local_file="clean_logs.sh",
                                  remote_file="/home/stack/clean_logs.sh",
                                  chown="stack:stack")
        # cleanup logs on all machines
        for node in cloud.nodes:
            node_ip = node[1]
            ssh.send_cmd("ssh heat-admin@{0} 'sudo bash -s' < clean_logs.sh".format(node_ip))
        cloud.prepare_tempest_directory(ssh)
        cloud.prepare_tempest_roles(ssh)
        cloud.prepare_tempest_identity(ssh)
        cloud.prepare_tempest_oslo()
        cloud.prepare_tempest_debug()
        cloud.prepare_tempest_services_enable()
        cloud.prepare_tempest_image(ssh)
        cloud.prepare_tempest_extension(ssh)
        cloud.add_neutron_public_network(ssh)
        cloud.prepare_tempest_public_net(ssh)
        cloud.prepare_tempest_conf_file(ssh)
        cloud.run_tempest_tests(ssh)
        cloud.collect_testr_tests(ssh, local_dest_dir=CWD)
        # collect logs from overcloud per box

        for node in cloud.nodes:
            node_name = node[0]
            node_ip = node[1]
            with utils.SSH(node_ip,
                           the_user="heat-admin",
                           key_file=CWD + "/id_rsa.tar.gz",
                           send_password=False) as ssh_node:
                # create tar.log file
                cloud.compress_logs(ssh_node, node_name + ".tar.gz", chown="heat-admin:heat-admin")
                cloud.copy_to_workspace(ssh_node, local_dest_dir=CWD,
                                        local_file=node_name + ".tar.gz",
                                        remote_file="/home/heat-admin/" + node_name + ".tar.gz")


