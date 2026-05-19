"""Cisco IOS / IOS-XE subscriber control policy augments."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal
from pydantic import BaseModel, Field

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.services import Services
from acex_devkit.models.composed_configuration import AugmentAttributes


# ---------------------------------------------------------------------------
# Builder classes — typed API for constructing policy-maps in config maps
# ---------------------------------------------------------------------------

@dataclass
class PolicyMapAction:
    priority: int
    action: str


@dataclass
class PolicyMapClass:
    priority: int
    class_name: str
    mode: str
    actions: List[PolicyMapAction] = field(default_factory=list)


@dataclass
class PolicyMapEvent:
    event_type: str
    match_type: str
    classes: List[PolicyMapClass] = field(default_factory=list)


def _events_to_dict(events: List[PolicyMapEvent]) -> dict:
    return {
        event.event_type: {
            "match_type": event.match_type,
            "classes": {
                str(cls.priority): {
                    "class_name": cls.class_name,
                    "mode": cls.mode,
                    "actions": {
                        str(act.priority): {"action": act.action}
                        for act in cls.actions
                    },
                }
                for cls in event.classes
            },
        }
        for event in events
    }


# ---------------------------------------------------------------------------
# Pydantic models — internal representation used by the renderer
# ---------------------------------------------------------------------------

class PolicyMapActionAttributes(BaseModel):
    action: str


class PolicyMapClassAttributes(BaseModel):
    class_name: str
    mode: str
    actions: Dict[str, PolicyMapActionAttributes] = Field(default_factory=dict)


class PolicyMapEventAttributes(BaseModel):
    match_type: str
    classes: Dict[str, PolicyMapClassAttributes] = Field(default_factory=dict)


class CiscoControlSubscriberPolicyMapAttributes(AugmentAttributes):
    type: Literal["cisco_control_subscriber_policy_map"] = "cisco_control_subscriber_policy_map"
    name: str
    events: Dict[str, PolicyMapEventAttributes] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# ConfigComponents
# ---------------------------------------------------------------------------

class CiscoControlSubscriberPolicyMap(Augment):
    type = "cisco_control_subscriber_policy_map"
    model_cls = CiscoControlSubscriberPolicyMapAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"
    singleton = False

    def pre_init(self):
        events = self.kwargs.get("events")
        if isinstance(events, list):
            self.kwargs["events"] = _events_to_dict(events)
        super().pre_init()


class CiscoServicePolicyControlSubscriberAttributes(AugmentAttributes):
    type: Literal["cisco_service_policy_control_subscriber"] = "cisco_service_policy_control_subscriber"
    policy_name: str


class CiscoServicePolicyControlSubscriber(Augment):
    type = "cisco_service_policy_control_subscriber"
    model_cls = CiscoServicePolicyControlSubscriberAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"

    def pre_init(self):
        pn = self.kwargs.get("policy_name")
        if isinstance(pn, CiscoControlSubscriberPolicyMap):
            self.kwargs["policy_name"] = pn.name
        super().pre_init()


class CiscoAccessSessionMonitorAttributes(AugmentAttributes):
    type: Literal["cisco_access_session_monitor"] = "cisco_access_session_monitor"
    enabled: bool = True


class CiscoAccessSessionMonitor(Augment):
    type = "cisco_access_session_monitor"
    model_cls = CiscoAccessSessionMonitorAttributes
    valid_targets = (Services,)
    default_vendor = "cisco"
