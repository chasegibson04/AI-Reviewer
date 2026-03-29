# Rigorous AI-Powered Scientific Manuscript Analysis

> **v0.2 Now Live:** The latest version of the AI Reviewer (v0.2) is now available at [https://www.rigorous.review/](https://www.rigorous.review/). Upload your manuscript, provide context on your target journal and receive structured feedback directly online via an interactive interface — now with progress tracking built in. Once initial testing of v0.2 is complete, we will make all module prompts open source to promote transparency and enable community contributions.

> **Help Us Improve!** Please provide feedback via [this short feedback form](https://docs.google.com/forms/d/1EhQvw-HdGRqfL01jZaayoaiTWLSydZTI4V0lJSvNpds) to help us improve the system.

> Support AI Reviewer v0.3 by rocking some *peer-reviewed merch* 👕🧠 – [grab yours here](https://rigorous-shop.fourthwall.com/) – GitHub contributors get free gear.

## Vision

This repository is intended for tools that make the creation, evaluation, and distribution of scientific knowledge more transparent, cheaper, faster, and better. Let's build this future together!

## Project Structure

- **Agent1_Peer_Review**: Multiagent AI review system for comprehensive manuscript analysis, detailed feedback, and PDF report generation (v0.1).
- **Agent2_Outlet_Fit**: (In Development) Tool for evaluating manuscript fit with target journals/conferences.

## Current Status

### Active Tools
- **Agent1_Peer_Review**: ✅ v0.1 Ready for use!
  - Comprehensive manuscript analysis with specialized agents
  - Detailed feedback on sections, scientific rigor, and writing quality (including quality control loops)
  - JSON output with actionable recommendations
  - PDF report generation
  - [📄 Detailed Documentation and Key Areas for Contribution](https://github.com/robertjakob/rigorous/blob/main/Agent1_Peer_Review/README.md)

### In Development
- **Agent2_Outlet_Fit**: 🚧 In Development
  - Core functionality being implemented
  - Integration with Agent1_Peer_Review in progress
  - Testing and validation ongoing
  - [🛠️ Development Plan](https://github.com/robertjakob/rigorous/blob/main/Agent2_Outlet_Fit/README.md)

### Future Modules and Ideas
- **Embedding-based similarity analysis** (by [@andjar](https://github.com/andjar)): Use embeddings (as in [*The landscape of biomedical research*](https://github.com/berenslab/pubmed-landscape)) to compare a paper’s abstract with existing literature. This could help surface uncited but relevant work and suggest suitable journals based on similarity clusters.
- Support for Drafting Reviewer Reponses.
- Feedback on Research Proposals and Protocols.
- AI-enabled document creation tool ("Cursor for Papers").
  
## Requirements

- Python 3.7+
- OpenAI API key (the system can be adapted to alternative LLMs, including locally hosted ones)
- PDF manuscripts to analyze
- Dependencies listed in each tool's requirements.txt

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Citation

If you use the Rigorous AI Reviewer in your research or project, please cite:

```bibtex
@software{rigorous_ai_reviewer2025,
  author = {Jakob, Robert and O'Sullivan, Kevin},
  title = {Rigorous AI Reviewer: Enabling AI for Scientific Manuscript Analysis},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/robertjakob/rigorous}
}
``` 

<p align="center">
  <img src="https://i.imgur.com/57BI7Ww.jpeg" width="400px" alt="Team Image"/>
</p>

<p align="center">
  <strong>Follow Robert</strong><br>
  <a href="https://www.linkedin.com/in/robertjakob/" style="margin-right: 10px;">
    <img src="https://img.shields.io/badge/LinkedIn-Robert-blue?logo=linkedin&style=social" alt="Follow Robert on LinkedIn">
  </a>
  <a href="https://x.com/robertjakob">
    <img src="https://img.shields.io/twitter/follow/robertjakob?style=social" alt="Follow @robertjakob on X">
  </a>
</p>

<p align="center">
  <strong>Follow Kevin</strong><br>
  <a href="https://www.linkedin.com/in/kevosull/">
    <img src="https://img.shields.io/badge/LinkedIn-Kevin-blue?logo=linkedin&style=social" alt="Follow Kevin on LinkedIn">
  </a>
</p>

<p align="center">
  Made with ❤️ in Zurich
</p>
