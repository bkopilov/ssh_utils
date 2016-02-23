
def source_stackrc():
    return "source /home/stack/stackrc"

def get_undercloud_nodes(ssh):
    nova_list = """nova list | awk '{print $4 " " $12}' | sed  's/=/ /g' """
    cmd = source_stackrc() + "&& " + nova_list
    nodes = ssh.send_cmd(cmd)
    print nodes
