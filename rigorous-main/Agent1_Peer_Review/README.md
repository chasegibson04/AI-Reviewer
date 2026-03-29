# Rigorous Reviewer (v0.1)
A multi-agent system for comprehensive manuscript analysis and review.

> **v0.2 Now Live:** The latest version of the AI Reviewer (v0.2) is now available at [https://www.rigorous.review/](https://www.rigorous.review/). Upload your manuscript, provide context on your target journal and review goals, and receive structured feedback directly online via an interactive interface — now with progress tracking built in. Once initial testing of v0.2 is complete, we will make all module prompts open source to promote transparency and enable community contributions.

> **Help Us Improve!** Please provide feedback via [this short feedback form](https://docs.google.com/forms/d/1EhQvw-HdGRqfL01jZaayoaiTWLSydZTI4V0lJSvNpds) to help us improve the system.

> Support AI Reviewer v0.3 by rocking some *peer-reviewed merch* 👕🧠 – [grab yours here](https://rigorous-shop.fourthwall.com/) – GitHub contributors get free gear.

## Overview

This project implements a sophisticated multi-agent system for analyzing academic manuscripts. The system uses a combination of section-specific, rigor, and writing quality agents to provide detailed feedback and suggestions for improvement. Each agent specializes in a specific aspect of manuscript analysis and provides structured JSON output.

## Join the Project

**We Need Your Help!** This a work in progress, which means:

- **Expect imperfections**: The system is continuously being improved
- **Your expertise matters**: Help us improve agent accuracy, especially specialized agents.

# Key Areas for Contribution to the AI Peer Reviewer

## 🧠 Agent Development & Specialization
- Build domain-specific agents for fields like medicine, economics, and computer science.
- Identify and articulate domain-specific principles of good research practice and responsible research conduct.
- Identify optimal foundation models for specific review tasks.

## 🧾 Prompt Engineering & Modularity
- Improve prompt quality for consistent, meaningful, and fair agent outputs.
- Refactor prompts into editable formats (e.g., `.txt`, `.json`) for easier debugging, iteration, and community feedback.

## 📝 Feedback Quality & Depth
- Enhance feedback relevance and contextuality.
- Help us figure out what constitutes a great review.
- Integrate Visual Language Models (VLMs) for figure and chart critique.
- Fix citation feedback by accurately detecting and formatting styles (APA, IEEE, etc.).
- Improve Feedback Report Layout and Style
- Add charts and illustration with review insights.
- Extract the most relevant points and highlight them in an additional section at the beginning of the report
- Help automate high-value, complex review tasks — such as assessing novelty, improving storyline and narrative flow, embedding research questions and findings within existing literature, and highlighting contributions without overselling them.
- Enable report personalization, allowing authors to specify focus areas (e.g. methodology, writing), preferred tone (e.g. critical, supportive), formatting preferences, or model selection (e.g., Nano vs. 4.1)
- Let authors preselect agents and review modules
- Let authors interact with review feedback via chat and ask follow-up questions
- Develop in-text feedback capabilities that highlight specific manuscript passages with contextual suggestions and inline comments.
- Enable review suggestions during the writing process (Cursor for papers)
- Agents with specialized roles and content access interact with each other to solve complex review questions collaboratively (e.g., via CrewAI, AutoGen, LangGraph)
- After reading only parts of the manuscript, agents reason about the rest and compare their own input against the paper (both top-down and bottom-up)
- Agents do a web search to compare content against what they find online (e.g., via Browser Use). This could involve checking recent publications, journal criteria, etc.

## 🎯 Accuracy & Reproducibility
- Boost analytical accuracy across formats and domains.
- Develop reproducibility agents that verify results based on shared code and data.
- Develop a robust scoring system across feedback categories that can be used to track improvements from v1 to v2

## 📚 Data & Knowledge Integration
- Build a RAG-ready database of preprints, reviews, and published papers.
- Collect journal/conference submission criteria for automatic formatting guidance.

## ⚙️ Scalability & Performance
- Parallelize the review pipeline for speed and batch processing.
- Support diverse input formats: PDF, `.docx`, LaTeX, Markdown, Overleaf, etc.

## 💬 User Feedback & Iteration
- Design a system for authors to rate and comment on individual review suggestions.
- Use this feedback to automatically identify high-value vs. low-value outputs.
- Enable fine-tuning of agents based on aggregated user response patterns.
- Users can interact with agents for follow-on questions. Based on these interactions, agents learn researcher preferences.

## 🐞 Known Bugs
- Report Generation can fail upon rare "<" ">" occurences in the feedback
- Citation Agent making unproper suggestions.
- special characters (e.g., ligatures) are falsely classified as typos

## 😤 Most Frequently Requested Changes
- Summarize the most impactful points at the beginning (the report is too long and focuses too heavily on language)

**Share your feedback**: Submit an issue with your ideas and suggestions. We want to know what kind of feedback you find useful, what is useless, and what you would expect in an ideal review report!

## Related Work
- [Open-Source Web Research Agents](https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart)
- [Reviewing Scientific Papers with AI](https://russpoldrack.substack.com/p/reviewing-scientific-papers-with-7a6)

# Agent Structure (v0.1)
## Specialized Agents (Reviewer Army)

The system currently includes 24 spezialized agents focusing on the following review criteria across three main categories. Think of them like a reviewer army bruteforcing your manuscript to find every potential isse.

### Section Agents (S1-S10)
- S1: Title and Keywords Analysis
- S2: Abstract Review
- S3: Introduction Assessment
- S4: Literature Review Analysis
- S5: Methodology Evaluation
- S6: Results Analysis
- S7: Discussion Review
- S8: Conclusion Assessment
- S9: References Analysis
- S10: Supplementary Materials Review

### Rigor Agents (R1-R7)
- R1: Originality and Contribution
- R2: Impact and Significance
- R3: Ethics and Compliance
- R4: Data and Code Availability
- R5: Statistical Rigor
- R6: Technical Accuracy
- R7: Consistency

### Writing Agents (W1-W7)
- W1: Language and Style
- W2: Narrative and Structure
- W3: Clarity and Conciseness
- W4: Terminology Consistency
- W5: Inclusive Language
- W6: Citation Formatting
- W7: Target Audience Alignment

Per default spezialised agents use GPT-4.1-nano (long-context, cost-efficient model). You can also choose another (local) model.

## Quality Control Agents
Quality Control Agent (think Associate Editor) serve as a validation layer across each category, they..
- Review and validate outputs from spezialized agents
- Ensure consistency and quality across analyses
- Provide a comprehensive final report with:
  - Validated scores and feedback
  - Critical remarks and improvement suggestions
  - Detailed explanations for each suggestion
  - Overall quality assessment
- Per default Quality Control Agents use GPT-4.1 for high-quality structured output. You can also choose another (local) model.

## Executive Summary Agent
The Executive Summary Agent provides a high-level synthesis through a two-step reasoning process:
1. Independent Review Generation
   - Analyzes the manuscript independently
   - Generates comprehensive review including summary, strengths/weaknesses, and suggestions
   - Focuses on target journal requirements and user priorities

2. Balanced Summary Generation
   - Synthesizes insights from both independent review and quality controlled results
   - Creates a unified executive summary in three paragraphs:
     * Overview of content and contribution
     * Balanced assessment of strengths and weaknesses
     * Actionable recommendations
   - Ensures natural flow while incorporating key insights
   - Maintains consistency with detailed assessment

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Configure your manuscript details in `manuscript.json`:
```json
{
    "manuscript_src": "path/to/your/manuscript.pdf",
    "publicationOutlets" : "e.g. Nature Medicine",
    "reviewFocus" : "e.g. Statistics and Writing"
}
```

2. Run the analysis:
```bash
python run_local_aipeer_review.py
```

The script will:
- Process your manuscript using all specialized agents
- Generate a comprehensive analysis
- Create a detailed PDF report
- Save the report in the `reports/` directory

Note: The analysis typically takes about 15 minutes to complete.

## Output

The system generates JSON files in the `results/` directory containing:
- Individual agent results (`{agent_name}_results.json`)
- Combined results (`combined_results.json`)
- Manuscript data (`manuscript_data.json`)
- Quality control results (`quality_control_results.json`)
- Executive summary (`executive_summary.json`)

Each agent's analysis follows a consistent JSON structure:

```json
{
    "score": int,  // Score from 1-5
    "critical_remarks": [
        {
            "category": str,
            "location": str,
            "issue": str,
            "severity": str,
            "impact": str
        }
    ],
    "improvement_suggestions": [
        {
            "location": str,
            "category": str,
            "focus": str,
            "original_text": str,
            "improved_version": str,
            "explanation": str
        }
    ],
    "detailed_feedback": {
        // Agent-specific detailed analysis
    },
    "summary": str  // Overall assessment summary
}
```

The executive summary follows a specific structure:
```json
{
    "manuscript_title": str,
    "executive_summary": str,  // Three-paragraph synthesis
    "independent_review": {
        "summary": str,
        "strengths_weaknesses": {
            "strengths": [str],
            "weaknesses": [str]
        },
        "critical_suggestions": [str]
    },
    "scores": {
        "section_score": float,
        "rigor_score": float,
        "writing_score": float,
        "final_score": float
    }
}
```

## Configuration

- Environment variables are managed in `.env`
- Agent configurations can be modified in `src/core/config.py`
- Model settings can be adjusted in `src/core/config.py`

## Development

### Project Structure
```
Agent1_Peer_Review/
├── src/
│   ├── reviewer_agents/
│   │   ├── section/      # Section agents (S1-S10)
│   │   ├── rigor/        # Rigor agents (R1-R7)
│   │   ├── writing/      # Writing agents (W1-W7)
│   │   ├── quality/      # Quality control agent
│   │   └── executive_summary_agent.py
│   ├── core/            # Core functionality and configuration
│   └── utils/           # Utility functions
├── manuscripts/         # Input manuscripts
├── reports/            # Generated PDF reports
├── manuscript.json     # Manuscript configuration
└── tests/             # Test suite
```

### Adding New Agents

1. Create a new agent class inheriting from `BaseReviewerAgent`
2. Implement the required analysis method
3. Add the agent to the controller's agent dictionary

## Manuscripts Folder

The `manuscripts` folder is where you should place the PDF manuscripts you want to analyze. Please ensure your PDF files are stored here before running the review process.

## Environment Configuration

A `.env` file is provided in this directory. You can add your OpenAI API key to this file as follows:

```
OPENAI_API_KEY=your_openai_api_key_here
```

Replace `your_openai_api_key_here` with your actual OpenAI API key.

## Setup Instructions

1. **Environment Setup**
   ```bash
   # Create and activate a virtual environment (optional but recommended)
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install required dependencies
   pip install -r requirements.txt
   ```

2. **API Key Configuration**
   - Create a `.env` file in the Agent1_Peer_Review directory
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     DEFAULT_MODEL=gpt-4.1-nano
     ```

3. **Manuscript Configuration**
   - Create or update `manuscript.json` with your manuscript details
   - Specify the PDF path and publication context
   - Define target journal and review focus areas

4. **Running the Analysis**
   ```bash
   python run_local_aipeer_review.py
   ```
   The script will process your manuscript and generate a PDF report in the `reports/` directory.

## Results

All results are saved in the `results`
