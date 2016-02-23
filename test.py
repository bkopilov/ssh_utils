import base64
import utils

if __name__ == "__main__":

    IP_ADDRESS = "MTI3LjAuMC4x"
    THE_USER = "cm9vdA=="
    THE_PASSWORD = "SWRvaGFtdWQ5IQ=="
    """ the password / ipv4 encrypted base64.b64encode("PASS")
        import base64
        print base64.b64encode()
        print base64.b64decode("cGFzc3dvcmQ=")
    """

    with utils.SSH(base64.b64decode(IP_ADDRESS),
                   the_user=base64.b64decode(THE_USER),
                   the_password=base64.b64decode(THE_PASSWORD)) as ssh:
        rep = ssh.send_cmd("ls -l")
        print rep




