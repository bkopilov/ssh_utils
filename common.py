
def source_stackrc():
    return "source /home/stack/stackrc"

def get_undercloud_nodes(ssh):
    cmd = source_stackrc() + "&& " + "nova list"
    nodes = ssh.send_cmd(cmd)
    print nodes
