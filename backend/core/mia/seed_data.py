"""
MIA Sample Seed Data.
Populates realistic emails including John Mathew (Inauguration),
John Thomas (Internship opportunity for ambiguity testing), Cyber Awareness, etc.
"""

import datetime
from typing import List, Dict, Any
from backend.core.mia.ingestion import email_ingestion_service
from backend.core.mia.storage import mia_storage


def get_sample_emails() -> List[Dict[str, Any]]:
    now = datetime.datetime.now(datetime.timezone.utc)

    return [
        {
            "email_id": "email-mia-001",
            "thread_id": "thread-mia-001",
            "sender_name": "John Mathew",
            "sender_email": "john.mathew@cyberdome.kerala.gov.in",
            "sender_domain": "cyberdome.kerala.gov.in",
            "subject": "Invitation to State-Level Inauguration: Project CLICK at Kerala Police Cyberdome",
            "body": (
                "Dear Boss,\n\n"
                "On behalf of Kerala Police Cyberdome, you are cordially invited to the State-Level Inauguration "
                "of Project CLICK (Cyber Learning & Intelligence Cyberdome Knowledgebase) on Friday at 10:00 AM "
                "at the Police Headquarters Auditorium, Trivandrum.\n\n"
                "The ceremony will be presided over by the State Police Chief and senior dignitaries. Keynote addresses "
                "will highlight regional cyber threat mitigation and our modern threat intelligence pipeline.\n\n"
                "Please confirm your attendance by Wednesday afternoon so that we may reserve your VIP seating pass.\n\n"
                "Warm regards,\n"
                "John Mathew\n"
                "Cyber Intelligence Officer, Cyberdome"
            ),
            "received_at": (now - datetime.timedelta(minutes=25)).isoformat(),
            "summary": "Invitation from John Mathew for the State-Level Inauguration of Project CLICK at Kerala Police Cyberdome in Trivandrum on Friday at 10:00 AM.",
            "main_topic": "Event Invitation",
            "purpose": "Invite recipient to the State-Level Inauguration of Project CLICK at Kerala Police Cyberdome",
            "events": ["CLICK State-Level Inauguration", "Project CLICK Inauguration"],
            "organizations": ["Kerala Police Cyberdome", "Cyberdome", "Kerala Police"],
            "locations": ["Trivandrum", "Police Headquarters Auditorium", "Kerala"],
            "activities": ["State-Level Inauguration ceremony", "Keynote address", "RSVP confirmation", "VIP pass"],
            "keywords": ["inauguration", "state-level", "cyberdome", "click", "trivandrum", "kerala police", "john mathew", "invitation", "ceremony"],
            "search_descriptions": [
                "invitation to state-level inauguration from john mathew",
                "state level inauguration cyberdome trivandrum",
                "project click inauguration invitation"
            ]
        },
        {
            "email_id": "email-mia-002",
            "thread_id": "thread-mia-002",
            "sender_name": "John Thomas",
            "sender_email": "john.thomas@techcorp-ai.org",
            "sender_domain": "techcorp-ai.org",
            "subject": "Internship Opportunity: Summer 2026 AI Research Fellowship at TechCorp AI Labs",
            "body": (
                "Hi,\n\n"
                "Following up on our discussions at the national AI summit, TechCorp AI Labs is officially opening "
                "applications for our Summer 2026 Research Fellowship.\n\n"
                "The internship position focuses on Autonomous Agent Systems, Subagent Orchestration, and Real-time Voice Processing. "
                "A competitive monthly stipend and full lab infrastructure access are provided.\n\n"
                "Please submit your resume and GitHub portfolio by the end of next week.\n\n"
                "Best regards,\n"
                "John Thomas\n"
                "Research Director, TechCorp AI Labs"
            ),
            "received_at": (now - datetime.timedelta(minutes=45)).isoformat(),
            "summary": "John Thomas invites applications for the Summer 2026 AI Research Fellowship internship at TechCorp AI Labs focusing on autonomous agent systems.",
            "main_topic": "Career Opportunity",
            "purpose": "Announce Summer 2026 AI Research Fellowship internship opportunity",
            "events": ["Summer 2026 AI Research Fellowship"],
            "organizations": ["TechCorp AI Labs", "TechCorp"],
            "locations": ["Online / Hybrid", "TechCorp Headquarters"],
            "activities": ["Submit resume", "GitHub portfolio submission", "AI research fellowship internship"],
            "keywords": ["internship", "opportunity", "fellowship", "ai research", "john thomas", "autonomous agents", "techcorp", "resume"],
            "search_descriptions": [
                "internship opportunity john thomas",
                "summer 2026 ai research fellowship techcorp",
                "autonomous agents internship opportunity"
            ]
        },
        {
            "email_id": "email-mia-003",
            "thread_id": "thread-mia-003",
            "sender_name": "Dr. Sarah Connor",
            "sender_email": "s.connor@nationalcyberdefense.org",
            "sender_domain": "nationalcyberdefense.org",
            "subject": "Cyber Awareness & First Responder Workshop Registration",
            "body": (
                "Greetings,\n\n"
                "Registration is officially open for the Cyber Awareness & First Responder Hands-On Workshop. "
                "This intensive training session covers active network defense, packet telemetry, and emergency incident containment.\n\n"
                "The workshop takes place on the 15th of this month via interactive virtual labs. "
                "Please register before Friday to secure lab credential provisioning.\n\n"
                "Regards,\n"
                "Dr. Sarah Connor\n"
                "National Cyber Defense Initiative"
            ),
            "received_at": (now - datetime.timedelta(hours=1, minutes=10)).isoformat(),
            "summary": "Dr. Sarah Connor announced registration for the Cyber Awareness and First Responder Workshop with interactive virtual labs on the 15th.",
            "main_topic": "Cyber Security Workshop",
            "purpose": "Register participants for the Cyber Awareness & First Responder Workshop",
            "events": ["Cyber Awareness & First Responder Workshop"],
            "organizations": ["National Cyber Defense Initiative", "Cyber Defense"],
            "locations": ["Virtual Labs", "Online"],
            "activities": ["Workshop registration", "Network defense training", "Lab credential provisioning"],
            "keywords": ["cyber awareness", "first responder", "workshop", "sarah connor", "incident response", "training"],
            "search_descriptions": [
                "cyber awareness workshop registration",
                "first responder workshop sarah connor",
                "cyber defense training registration"
            ]
        },
        {
            "email_id": "email-mia-004",
            "thread_id": "thread-mia-004",
            "sender_name": "AWS Cloud Billing",
            "sender_email": "billing@amazon.com",
            "sender_domain": "amazon.com",
            "subject": "AWS Cloud Billing Alert: Monthly Infrastructure Usage Statement",
            "body": (
                "Hello,\n\n"
                "This is an automated notification regarding your Amazon Web Services monthly cloud infrastructure spend. "
                "Total accrued charges for EC2, S3, and Vector Databases are currently within your allocated budget threshold.\n\n"
                "Detailed line-item breakdowns are available in your AWS Billing Console.\n\n"
                "Amazon Web Services"
            ),
            "received_at": (now - datetime.timedelta(hours=3, minutes=30)).isoformat(),
            "summary": "Monthly AWS infrastructure billing statement showing charges are within the budget threshold.",
            "main_topic": "Cloud Billing",
            "purpose": "Monthly cloud infrastructure spending report",
            "events": [],
            "organizations": ["Amazon Web Services", "AWS"],
            "locations": ["Cloud"],
            "activities": ["Review billing dashboard"],
            "keywords": ["aws", "cloud", "billing", "amazon", "infrastructure", "charges", "statement"],
            "search_descriptions": [
                "aws billing alert cloud usage",
                "amazon web services invoice statement"
            ]
        },
        {
            "email_id": "email-mia-005",
            "thread_id": "thread-mia-005",
            "sender_name": "Alice Walker",
            "sender_email": "alice.walker@atlas-project.internal",
            "sender_domain": "atlas-project.internal",
            "subject": "Project ATLAS 2.0 Sprint Review & Architectural Sign-off",
            "body": (
                "Hi Boss,\n\n"
                "The engineering team has wrapped up the Sprint Review for ATLAS 2.0. "
                "The biometric gate and Antigravity bridge have cleared all acceptance benchmarks. "
                "The MIA subagent module is slated for final integration verification today.\n\n"
                "Best,\n"
                "Alice Walker\n"
                "Lead Systems Architect"
            ),
            "received_at": (now - datetime.timedelta(minutes=10)).isoformat(),
            "summary": "Alice Walker confirms ATLAS 2.0 sprint review completion and MIA subagent integration sign-off.",
            "main_topic": "Engineering Sprint Review",
            "purpose": "Confirm sprint review completion and architectural sign-off for ATLAS 2.0",
            "events": ["ATLAS 2.0 Sprint Review"],
            "organizations": ["ATLAS Engineering Team"],
            "locations": ["Internal"],
            "activities": ["Sprint review", "MIA integration verification"],
            "keywords": ["atlas", "sprint review", "architectural sign-off", "alice walker", "subagents", "mia"],
            "search_descriptions": [
                "atlas 2.0 sprint review alice walker",
                "architectural sign-off email atlas"
            ]
        }
    ]


async def seed_sample_emails_if_empty(force: bool = False):
    """Seeds sample emails into SQLite if table is empty or if forced."""
    stats = mia_storage.get_stats()
    if stats["total_emails"] > 0 and not force:
        return stats

    if force:
        mia_storage.clear_all()

    samples = get_sample_emails()
    for email in samples:
        await email_ingestion_service.ingest_email(email)

    return mia_storage.get_stats()
