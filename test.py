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
        cloud.run_cloud_cleanup(ssh)
        cloud.get_undercloud_nodes(ssh)
        cloud.show_overcloud_nodes()
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
