"""
MIA (Mail Intelligence Assistant) Agent Module.
Parses and executes MIA command specifications:
  - Format A: mia: name(SEARCH_QUERY)
  - Format B: mia: content(SEARCH_QUERY)
  - Format C: mia: summary() or mia: summary(HOURS)
Enforces ambiguity handling, returns stored summaries directly without re-summarization LLM calls,
and provides dual responses: rich visual text and clean TTS spoken speech.
"""

import re
import datetime
from typing import Dict, Any, Tuple, Optional
from backend.config import config_manager
from backend.core.mia.storage import mia_storage
from backend.core.mia.search import hybrid_search_engine
from backend.core.mia.ingestion import email_ingestion_service

RE_MIA_COMMAND = re.compile(r"^mia\s*:\s*(.+)$", re.IGNORECASE)
RE_MIA_NAME = re.compile(r"^name\s*\(\s*(.*?)\s*\)$", re.IGNORECASE)
RE_MIA_CONTENT = re.compile(r"^content\s*\(\s*(.*?)\s*\)$", re.IGNORECASE)
RE_MIA_SUMMARY = re.compile(r"^summary\s*(?:\(\s*(\d*\.?\d*)\s*\))?$", re.IGNORECASE)


class MIAAgent:
    def __init__(self):
        pass

    def check_llm_status(self) -> Tuple[bool, str]:
        """Validates if an active LLM is configured for MIA."""
        return email_ingestion_service.check_llm_configured()

    async def execute(self, command_text: str) -> Dict[str, Any]:
        """
        Executes an incoming 'mia:' command.
        Returns:
            {
                "success": bool,
                "response": str (visual text),
                "tts_text": str (clean spoken text),
                "subcommand": str,
                "status": str
            }
        """
        cleaned = command_text.strip()
        match = RE_MIA_COMMAND.match(cleaned)
        if not match:
            return {
                "success": False,
                "response": "Invalid MIA command syntax. Use `mia: name(...)`, `mia: content(...)`, or `mia: summary()`.",
                "tts_text": "Invalid MIA command syntax.",
                "subcommand": "unknown",
                "status": "error"
            }

        instruction = match.group(1).strip()

        # Check if LLM is configured
        has_llm, llm_msg = self.check_llm_status()
        if not has_llm:
            err_msg = (
                "⚠️ **MIA Error**: No active LLM configured for MIA.\n\n"
                f"Reason: {llm_msg}\n\n"
                "Please configure an LLM provider (or provide a valid API key) in the "
                "**Control Panel ➔ Subagents ➔ MIA** tab."
            )
            return {
                "success": False,
                "response": err_msg,
                "tts_text": "MIA Error: No LLM configured. Please configure an LLM in the Control Panel under Subagents.",
                "subcommand": "llm_missing",
                "status": "no_llm_error"
            }

        # Check Format A: mia: name(...)
        name_match = RE_MIA_NAME.match(instruction)
        if name_match:
            query = name_match.group(1).strip()
            return await self._handle_name_search(query)

        # Check Format B: mia: content(...)
        content_match = RE_MIA_CONTENT.match(instruction)
        if content_match:
            query = content_match.group(1).strip()
            return await self._handle_content_search(query)

        # Check Format C: mia: summary() or mia: summary(HOURS)
        summary_match = RE_MIA_SUMMARY.match(instruction)
        if summary_match:
            hours_str = summary_match.group(1)
            hours = float(hours_str) if hours_str and hours_str.strip() else None
            return await self._handle_summary(hours)

        # Fallback lenient matching if user omitted parentheses
        if instruction.lower().startswith("name "):
            query = instruction[5:].strip()
            return await self._handle_name_search(query)
        if instruction.lower().startswith("content "):
            query = instruction[8:].strip()
            return await self._handle_content_search(query)
        if instruction.lower() in ("summary", "summary()"):
            return await self._handle_summary(None)

        return {
            "success": False,
            "response": (
                f"Unknown MIA action '{instruction}'. Supported commands:\n"
                "- `mia: name(SEARCH_QUERY)` — Search by sender name, email, or domain\n"
                "- `mia: content(SEARCH_QUERY)` — Hybrid semantic content search\n"
                "- `mia: summary()` or `mia: summary(HOURS)` — Concise digest of recent emails"
            ),
            "tts_text": "Unknown MIA action. Supported actions are name search, content search, and summary.",
            "subcommand": "unknown",
            "status": "error"
        }

    async def _handle_name_search(self, query: str) -> Dict[str, Any]:
        """
        Format A: mia: name(SEARCH_QUERY)
        Searches sender_name, sender_email, sender_domain (case-insensitive, normalized whitespace).
        Handles ambiguity if multiple distinct senders match.
        """
        if not query:
            return {
                "success": False,
                "response": "Please provide a sender name, email, or domain to search. Example: `mia: name(John)`.",
                "tts_text": "Please provide a sender name to search.",
                "subcommand": "name",
                "status": "error"
            }

        emails, distinct_senders = mia_storage.search_by_sender(query)

        if not emails:
            msg = f"No emails found from sender matching **'{query}'**."
            return {
                "success": False,
                "response": msg,
                "tts_text": f"No emails found from sender matching {query}.",
                "subcommand": "name",
                "status": "not_found"
            }

        # Ambiguity Handling: Multiple distinct senders matched
        if len(distinct_senders) > 1:
            senders_list_text = []
            for i, s in enumerate(distinct_senders, 1):
                email_str = f" ({s['email']})" if s.get("email") else ""
                senders_list_text.append(f"{i}. **{s['name'] or 'Unknown'}**{email_str}")

            lines = [
                f"🔍 Multiple matching senders found for **'{query}'**:",
                "",
                *senders_list_text,
                "",
                "Please specify which sender you'd like to check (e.g. `mia: name(John Mathew)` or `mia: name(John Thomas)`)."
            ]
            response_text = "\n".join(lines)
            tts_text = f"Multiple matching senders found for {query}: {', '.join(s['name'] for s in distinct_senders)}. Please specify which sender you'd like to check."

            return {
                "success": True,
                "response": response_text,
                "tts_text": tts_text,
                "subcommand": "name",
                "status": "ambiguous",
                "distinct_senders": distinct_senders
            }

        # Single sender matched: return matching emails with Subject and Summary
        sender = distinct_senders[0]
        sender_label = sender["name"] or sender["email"]
        lines = [
            f"📬 **Found {len(emails)} email(s) from {sender_label}**:\n"
        ]

        for i, em in enumerate(emails, 1):
            dt_str = em.get("received_at", "")[:16].replace("T", " ")
            lines.append(f"**{i}. {em.get('subject', 'No Subject')}**")
            lines.append(f"   *Received:* {dt_str} UTC")
            lines.append(f"   *Summary:* {em.get('summary', 'No summary available.')}")
            lines.append("")

        response_text = "\n".join(lines).strip()
        top_subj = emails[0].get("subject", "")
        tts_text = f"Found {len(emails)} email from {sender_label}. Subject: {top_subj}. {emails[0].get('summary', '')}"

        return {
            "success": True,
            "response": response_text,
            "tts_text": tts_text,
            "subcommand": "name",
            "status": "found",
            "emails": emails
        }

    async def _handle_content_search(self, query: str) -> Dict[str, Any]:
        """
        Format B: mia: content(SEARCH_QUERY)
        Hybrid parallel search (K + S + V + E) with confidence and ambiguity management.
        Returns stored summary directly without re-summarization LLM calls.
        """
        if not query:
            return {
                "success": False,
                "response": "Please provide a query for content search. Example: `mia: content(State-Level Inauguration)`.",
                "tts_text": "Please provide a query for content search.",
                "subcommand": "content",
                "status": "error"
            }

        search_res = await hybrid_search_engine.hybrid_search(query)
        status = search_res.get("status")

        if status == "not_found":
            msg = f"🔍 No relevant emails found matching your query: **'{query}'**."
            return {
                "success": False,
                "response": msg,
                "tts_text": f"No relevant emails found matching your query for {query}.",
                "subcommand": "content",
                "status": "not_found"
            }

        if status == "ambiguous":
            candidates = search_res.get("candidates", [])
            lines = [
                f"⚠️ Multiple relevant emails found matching **'{query}'** with similar confidence scores:",
                ""
            ]
            for i, cand in enumerate(candidates, 1):
                sender = cand.get("sender_name") or cand.get("sender_email")
                dt = cand.get("received_at", "")[:16].replace("T", " ")
                lines.append(f"{i}. **{cand.get('subject')}**")
                lines.append(f"   *From:* {sender} ({dt})")
                lines.append(f"   *Topic:* {cand.get('main_topic', 'General')}")
                lines.append("")

            lines.append("Please clarify which email you are looking for by specifying the sender or exact topic.")
            response_text = "\n".join(lines).strip()
            tts_text = f"Multiple close email matches found for {query}. Please clarify between {candidates[0].get('subject')} or {candidates[1].get('subject')}."

            return {
                "success": True,
                "response": response_text,
                "tts_text": tts_text,
                "subcommand": "content",
                "status": "ambiguous",
                "candidates": candidates
            }

        # Status == 'found': Return stored summary directly without LLM re-summarization
        top_email = search_res.get("top_email")
        if not top_email:
            return {
                "success": False,
                "response": f"No relevant email found for '{query}'.",
                "tts_text": "No relevant email found.",
                "subcommand": "content",
                "status": "not_found"
            }

        sender = top_email.get("sender_name") or top_email.get("sender_email")
        dt_str = top_email.get("received_at", "")[:16].replace("T", " ")
        score_pct = int(search_res.get("top_score", 0.0) * 100)

        lines = [
            f"🎯 **Best Matching Email ({score_pct}% Match)**:",
            f"**Subject**: {top_email.get('subject')}",
            f"**From**: {sender} <{top_email.get('sender_email')}>",
            f"**Date**: {dt_str} UTC",
            f"**Category**: {top_email.get('main_topic', 'General')}",
            "",
            f"📋 **Summary**:",
            top_email.get("summary", "No summary stored."),
            ""
        ]

        if top_email.get("events"):
            lines.append(f"• **Events**: {', '.join(top_email['events'])}")
        if top_email.get("locations"):
            lines.append(f"• **Locations**: {', '.join(top_email['locations'])}")
        if top_email.get("activities"):
            lines.append(f"• **Key Actions**: {', '.join(top_email['activities'])}")

        response_text = "\n".join(lines).strip()
        tts_text = f"Found email from {sender} regarding {top_email.get('subject')}. Summary: {top_email.get('summary')}"

        return {
            "success": True,
            "response": response_text,
            "tts_text": tts_text,
            "subcommand": "content",
            "status": "found",
            "email": top_email,
            "score": search_res.get("top_score")
        }

    async def _handle_summary(self, hours: Optional[float] = None) -> Dict[str, Any]:
        """
        Format C: mia: summary() or mia: summary(HOURS)
        Lists out and provides a concise digest of emails received in the past N hours.
        """
        cfg = config_manager.get("mia", {})
        if hours is None or hours <= 0:
            hours = float(cfg.get("summary_hours", 2.0))

        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
        recent_emails = mia_storage.get_emails_since(cutoff)

        if not recent_emails:
            # Fallback check: if sample emails exist but were seeded earlier, inform user clearly
            all_emails = mia_storage.get_all_emails()
            if not all_emails:
                msg = f"No emails currently stored in MIA. Run sample seeding or ingest emails first."
            else:
                msg = (
                    f"📬 No emails received in the past **{hours:.1f} hour(s)**.\n"
                    f"(Total emails in database: {len(all_emails)}. Try a larger window, e.g. `mia: summary(24)`.)"
                )
            return {
                "success": True,
                "response": msg,
                "tts_text": f"No emails received in the past {int(hours)} hours.",
                "subcommand": "summary",
                "status": "empty",
                "emails": []
            }

        lines = [
            f"📊 **MIA Email Digest (Past {hours:.1f} hours — {len(recent_emails)} email{'s' if len(recent_emails) != 1 else ''})**:\n"
        ]

        # Cloud LLM Executive Summarization
        executive_summary = None
        llm_cfg, ok = email_ingestion_service._get_mia_llm_config()
        if ok and llm_cfg and len(recent_emails) >= 1:
            try:
                from backend.core.llm_hub import llm_hub
                email_briefs = []
                for e in recent_emails[:6]:
                    email_briefs.append(f"- From: {e.get('sender_name')} | Subject: {e.get('subject')} | Topic: {e.get('main_topic')} | Summary: {e.get('summary')}")
                prompt_text = (
                    f"Boss received the following emails in the past {hours:.1f} hours:\n"
                    + "\n".join(email_briefs)
                    + "\n\nProvide a razor-sharp, high-signal executive briefing for Boss. "
                    "Extract ONLY actionable items, critical deadlines, dates, and urgent decisions. "
                    "Zero pleasantries, zero fluff. Pure high-density facts in 1-2 direct sentences."
                )
                cloud_resp = await llm_hub.generate_response(
                    prompt=prompt_text,
                    config=llm_cfg,
                    system_prompt="You are MIA, Boss's elite executive Mail Intelligence Assistant. Deliver ultra-crisp, high-density briefings focused exclusively on critical facts, deadlines, and required actions."
                )
                if cloud_resp and not cloud_resp.startswith("LLM execution error") and "error" not in cloud_resp.lower() and "invalid" not in cloud_resp.lower():
                    executive_summary = cloud_resp.strip()
                    lines.append(f"⚡ **Cloud AI Executive Briefing**:\n{executive_summary}\n")
            except Exception as e_llm:
                print(f"[MIA Cloud Summarization]: {e_llm}")

        tts_items = []
        for i, em in enumerate(recent_emails, 1):
            sender = em.get("sender_name") or em.get("sender_email")
            lines.append(f"**{i}. {em.get('subject')}**")
            lines.append(f"   *Sender:* {sender} | *Topic:* {em.get('main_topic', 'General')}")
            lines.append(f"   *Summary:* {em.get('summary', 'No summary available.')}")
            lines.append("")
            tts_items.append(f"{sender} about {em.get('subject')}")

        response_text = "\n".join(lines).strip()
        # Build razor-sharp spoken readout for MIA summaries (pure relevant data)
        tts_parts = []
        if executive_summary:
            tts_parts.append(f"Boss, here is your briefing for the past {int(hours)} hours: {executive_summary}")
        else:
            tts_parts.append(f"Boss, you received {len(recent_emails)} email{'s' if len(recent_emails) != 1 else ''} in the past {int(hours)} hours.")

        for i, em in enumerate(recent_emails, 1):
            sender = em.get("sender_name") or em.get("sender_email")
            subj = em.get("subject", "No subject")
            summ = em.get("summary", "")
            tts_parts.append(f"Item {i}, from {sender}: {subj}. {summ}")

        tts_text = " ".join(tts_parts)

        return {
            "success": True,
            "response": response_text,
            "tts_text": tts_text,
            "subcommand": "summary",
            "status": "digest_ready",
            "emails": recent_emails
        }


mia_agent = MIAAgent()
