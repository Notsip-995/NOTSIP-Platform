from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum

class Risk(IntEnum):
    LOW=0; MEDIUM=1; HIGH=2; CRITICAL=3

@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    risk: Risk
    requires_confirmation: bool=False
    destructive: bool=False

CAPABILITIES = {
    'read_files': Capability('read_files','Read authorized files',Risk.LOW),
    'write_files': Capability('write_files','Write authorized files',Risk.MEDIUM, True),
    'computer_control': Capability('computer_control','Control the Windows node',Risk.HIGH, True),
    'internet_search': Capability('internet_search','Retrieve current public information',Risk.LOW),
    'calendar_read': Capability('calendar_read','Read calendar data',Risk.LOW),
    'calendar_write': Capability('calendar_write','Create or modify calendar data',Risk.MEDIUM, True),
    'email_read': Capability('email_read','Read connected mail',Risk.LOW),
    'email_send': Capability('email_send','Send email or messages',Risk.HIGH, True),
    'phone_control': Capability('phone_control','Operate the paired Android device',Risk.HIGH, True),
    'system_admin': Capability('system_admin','Administrative system changes',Risk.CRITICAL, True, True),
    'robotics': Capability('robotics','Operate a real robotics endpoint',Risk.CRITICAL, True, True),
    'satellite': Capability('satellite','Access configured remote sensing systems',Risk.MEDIUM, True),
}

def catalog() -> list[dict]:
    return [c.__dict__ | {'risk': int(c.risk)} for c in CAPABILITIES.values()]
