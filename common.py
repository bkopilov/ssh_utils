
def source_stackrc():
    return "su - stack && source ~/stackrc "

def get_undercloud_nodes(ssh):
    cmd = source_stackrc() + "&&" + "nova list"
    nodes = ssh.send_cmd(cmd)
    print nodes
