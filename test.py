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

        common.get_undercloud_nodes(ssh)
