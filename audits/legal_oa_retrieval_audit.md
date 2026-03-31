# Legal OA Retrieval Audit

## Prior State Findings
- **TLS Spoofing:** `citation_fetcher.py` was actively disabling SSL/TLS verification during retry attempts (`verify=not is_retry`). This is a critical security vulnerability and an unprofessional scraping tactic.
- **User-Agent Spoofing:** The module hardcoded a fake Chrome/Windows browser user-agent to bypass basic bot protection.
- **Sci-Hub / Illegal Access:** No direct Sci-Hub URL usage was found in the core execution pipeline (only an inactive Colab notebook `Copy of PaperScraperV2.ipynb` contained references to it). However, the TLS bypass and spoofing mirrored adversarial scraping tactics.

## Improvements Implemented
- **Standardized Bot Identification:** Replaced the spoofed User-Agent with a transparent, standard bot string (`AI-Reviewer-Bot/1.0 (Research Validation; +https://github.com/example/ai-reviewer)`).
- **Strict TLS Enforcement:** Removed the `verify=not is_retry` logic. All requests are now strictly `verify=True` to maintain compliance and security.
- **Library Compliance:** Ensured that `requests.get` properly utilizes the transparent headers across all download functions.

## Conclusion
The retrieval pipeline is now completely "above board", operating exclusively through legitimate API requests (Unpaywall, Semantic Scholar, etc.) and standard, identified HTTP requests for OA PDFs, fully eliminating adversarial bypass mechanics.