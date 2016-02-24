import base64
import utils
import common
if __name__ == "__main__":

    IP_ADDRESS = "MTkyLjE2OC4yNTAuMjAy"
    THE_USER = "c3RhY2s="
    THE_PASSWORD = "MVMwbHV0MW9uIQ=="
    """ the password / ipv4 encrypted base64.b64encode("PASS")
        import base64
        print base64.b64encode()
        print base64.b64decode("cGFzc3dvcmQ=")
    """

    with utils.SSH(base64.b64decode(IP_ADDRESS),
                   the_user=base64.b64decode(THE_USER),
                   the_password=base64.b64decode(THE_PASSWORD)) as ssh:
        cloud = common.UnderCloud()
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
        cloud.prepare_tempest_conf_file(ssh)
        cloud.run_tempest_tests(ssh)

