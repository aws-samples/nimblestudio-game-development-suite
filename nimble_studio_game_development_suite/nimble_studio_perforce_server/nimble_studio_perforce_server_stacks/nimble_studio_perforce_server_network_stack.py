from aws_cdk import (
    Tags,
    aws_ec2 as ec2,
)
from constructs import Construct
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_common_stack import (
    NimbleStudioPerforceServerCommonStack,
)
from ipaddress import ip_network


class NimbleStudioPerforceServerNetworkStack(NimbleStudioPerforceServerCommonStack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        studio_vpc: ec2.IVpc = self._vpc
        vpc_cidr = ip_network(self._vpc_cidr)

        # NACL Entry
        self._nacl.add_entry(
            "WorkstationSupportNACLEntrySwarmServer",
            cidr=ec2.AclCidr.ipv4(str(vpc_cidr)),
            rule_action=ec2.Action.ALLOW,
            rule_number=222,
            traffic=ec2.AclTraffic.tcp_port(port=80),
            direction=ec2.TrafficDirection.INGRESS,
        )

        # Security Group

        self.perforce_server_security_group = ec2.SecurityGroup(
            self,
            "PerforceServerSecurityGroup",
            vpc=studio_vpc,
            allow_all_outbound=True,
            description="Security group for the perforce server",
        )
        Tags.of(self.perforce_server_security_group).add(
            "Name", f"Perforce-{self._stage}"
        )

        self.perforce_server_security_group.add_ingress_rule(
            self._workstations_sg,
            ec2.Port.tcp(1666),
            "Allow TCP 1666 access from the Workstations SG",
        )
        self.perforce_server_security_group.add_ingress_rule(
            self._workstations_sg,
            ec2.Port.tcp(3389),
            "Allow TCP 3389 access from the Workstations SG",
        )
        self.perforce_server_security_group.add_ingress_rule(
            self._workstations_sg,
            ec2.Port.tcp(80),
            "Allow TCP 80 access from the Workstations SG",
        )
        self.perforce_server_security_group.connections.allow_from(
            self.perforce_server_security_group,
            ec2.Port.tcp(1666),
            "Allow TCP 1666 access from the security group",
        )
        self.perforce_server_security_group.connections.allow_from(
            self.perforce_server_security_group,
            ec2.Port.tcp(3389),
            "Allow TCP 3389 access from the security group",
        )
        self.perforce_server_security_group.connections.allow_from(
            self.perforce_server_security_group,
            ec2.Port.tcp(80),
            "Allow TCP 80 access from the security group",
        )

        if self._vpce_sg:
            self._vpce_sg.add_ingress_rule(
                self.perforce_server_security_group,
                ec2.Port.tcp(443),
                description=f"from {self.perforce_server_security_group.unique_id}:443",
            )
