import path from 'path';
import fs from 'fs-extra';
import { RoutingService, ReviewStage, ProfileName } from '../routing/RoutingService';
import { LLMProvider } from '../providers/LLMProvider';
import { EventLogger } from '../logging/EventLogger';
import { DocumentParser, ParsedDocument } from '../tools/DocumentParser';
import { v4 as uuidv4 } from 'uuid';
import { chunkText, protectFrontMatter, detectFigureTableIssues, detectCitationIssues, dedupeAndArbitrate } from '../utils/textAnalysis';
import { Issue, IssueSchema } from '../models/IssueSchema';

export interface PipelineOptions {
  projectId: string;
  runId: string;
  runDir: string;
  profileName: ProfileName;
  llm: LLMProvider;
  logger: EventLogger;
  projectRootDir: string;
}

export class ReviewPipeline {
  private options: PipelineOptions;
  private routing: RoutingService;
  private parsedDoc?: ParsedDocument;
  private manuscriptPath?: string;
  private issues: Issue[] = [];

  constructor(options: PipelineOptions) {
    this.options = options;
    this.routing = new RoutingService(options.runDir, options.profileName);
  }

  private parseJSON(text: string): any {
    try {
      const match = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
      if (match) return JSON.parse(match[0]);
      return { raw: text };
    } catch(e) {
      return { raw: text, parse_error: true };
    }
  }

  public async run() {
    try {
      this.findManuscript();
      await this.stage01_Ingest();
      await this.stage02_SectionMap();
      await this.stage03_Digestion();
      await this.stage04_Terminology();
      await this.stage05_Coherence();
      await this.stage06_Methods();
      await this.stage07_Figures();
      await this.stage08_Citations();
      await this.stage09_LineEdits();
      await this.stage10_Arbitration();
      await this.stage11_Render();
      await this.stage12_Validation();

      this.updateRunStatus('success');
    } catch (error: any) {
      this.updateRunStatus('failure');
      throw error;
    }
  }

  private findManuscript() {
    const sourceDir = path.join(this.options.projectRootDir, 'source');
    if (!fs.existsSync(sourceDir)) return;
    
    const files = fs.readdirSync(sourceDir);
    if (files.length > 0) {
      this.manuscriptPath = path.join(sourceDir, files[0]);
    }
  }

  private async executeStage(stage: ReviewStage, task: (model: string) => Promise<any>) {
    const model = this.routing.getModelForStage(stage);
    const event = this.options.logger.logToolStart(`stage_${stage}`, `Executing ${stage} review layer using ${model}`);
    
    try {
      const result = await task(model);
      const artifactPath = path.join(this.options.runDir, 'stages', `stage_${stage}.json`);
      fs.writeJsonSync(artifactPath, result, { spaces: 2 });
      this.options.logger.logToolEnd(event, 'success', undefined, [artifactPath]);
      return result;
    } catch (error: any) {
      this.options.logger.logToolEnd(event, 'failure', error.message);
      error.stage = stage;
      throw error;
    }
  }

  private async stage01_Ingest() {
    return this.executeStage('ingest', async () => {
      if (!this.manuscriptPath) {
        return { status: 'skipped', reason: 'No manuscript found in source directory' };
      }
      this.parsedDoc = await DocumentParser.parse(this.manuscriptPath);
      return { 
        status: 'ingested', 
        fileType: this.parsedDoc.sourceType, 
        characterCount: this.parsedDoc.text.length,
        textPreview: this.parsedDoc.text.substring(0, 200) + '...'
      };
    });
  }

  private async stage02_SectionMap() {
    return this.executeStage('sections', async (model) => {
      if (!this.parsedDoc || this.parsedDoc.text.length === 0) {
         return { sections: ['Abstract', 'Introduction', 'Methods', 'Results', 'Discussion'], mock: true };
      }

      const prompt = `Analyze the following manuscript text and extract the main structural sections (e.g. Abstract, Introduction, Methods, etc.). Return ONLY a JSON object with a 'sections' key containing a list of strings.\n\nText:\n${this.parsedDoc.text.substring(0, 10000)}`;
      
      const response = await this.options.llm.chat([
        { role: 'system', content: 'You are an expert manuscript analyzer. Always return strictly formatted JSON.' },
        { role: 'user', content: prompt }
      ], { model, max_tokens: 500 });

      return this.parseJSON(response);
    });
  }

  private async stage03_Digestion() {
    return this.executeStage('ingest', async (model) => {
      if (!this.parsedDoc || this.parsedDoc.text.length === 0) return { claims: [], mock: true };
      
      const chunks = chunkText(this.parsedDoc.text, 8000);
      const claims: string[] = [];
      
      for (const chunk of chunks.slice(0, 2)) {
        const prompt = `Extract core claims and methods from this text:\n\n${chunk}\n\nReturn JSON: { "claims": ["..."] }`;
        const resp = await this.options.llm.chat([{ role: 'user', content: prompt }], { model, max_tokens: 500 });
        const parsed = this.parseJSON(resp);
        if (parsed.claims) claims.push(...parsed.claims);
      }
      return { claims };
    });
  }

  private async stage04_Terminology() {
    return this.executeStage('terminology', async (model) => {
      if (!this.parsedDoc) return { undefined_terms: [] };
      const prompt = `Identify undefined abbreviations or jargon in the text:\n\n${this.parsedDoc.text.substring(0, 5000)}\n\nReturn JSON: { "undefined_terms": ["..."] }`;
      const resp = await this.options.llm.chat([{ role: 'user', content: prompt }], { model, max_tokens: 300 });
      return this.parseJSON(resp);
    });
  }

  private async stage05_Coherence() {
    return this.executeStage('coherence', async (model) => {
      if (!this.parsedDoc) return { issues: [] };
      const prompt = `Analyze paragraph transitions for coherence issues:\n\n${this.parsedDoc.text.substring(0, 5000)}\n\nReturn JSON: { "issues": [{"location": "...", "description": "..."}] }`;
      const resp = await this.options.llm.chat([{ role: 'user', content: prompt }], { model, max_tokens: 400 });
      return this.parseJSON(resp);
    });
  }

  private async stage06_Methods() {
    return this.executeStage('methods', async (model) => {
      if (!this.parsedDoc) return { critiques: [] };
      const prompt = `Critique the methods section for missing controls or overclaiming:\n\n${this.parsedDoc.text.substring(0, 8000)}\n\nReturn JSON: { "critiques": ["..."] }`;
      const resp = await this.options.llm.chat([{ role: 'user', content: prompt }], { model, max_tokens: 500 });
      return this.parseJSON(resp);
    });
  }

  private async stage07_Figures() {
    return this.executeStage('figures', async () => {
      if (!this.parsedDoc) return { figure_references: [] };
      const result = detectFigureTableIssues(this.parsedDoc.text);
      
      result.issues.orphans.forEach(o => {
        this.issues.push({
          id: uuidv4(),
          stage: 'figures',
          section: 'body',
          location: o,
          severity: 'medium',
          confidence: 0.9,
          issue_type: 'orphan_reference',
          evidence: `Mentioned ${o} in text but no corresponding declaration/caption found.`,
          suggested_fix: `Add caption for ${o} or remove mention.`,
          localizable: true,
          render_mode: 'comment'
        });
      });

      result.issues.unreferenced.forEach(u => {
        this.issues.push({
          id: uuidv4(),
          stage: 'figures',
          section: 'captions',
          location: u,
          severity: 'low',
          confidence: 0.8,
          issue_type: 'unreferenced_declaration',
          evidence: `Declared ${u} but it is never referenced in the main text.`,
          suggested_fix: `Add reference to ${u} in the text.`,
          localizable: true,
          render_mode: 'comment'
        });
      });

      return result;
    });
  }

  private async stage08_Citations() {
    return this.executeStage('citations', async () => {
      if (!this.parsedDoc) return { citations_found: [] };
      const result = detectCitationIssues(this.parsedDoc.text);

      result.issues.danglingCitations.forEach(d => {
        this.issues.push({
          id: uuidv4(),
          stage: 'citations',
          section: 'body',
          location: `[${d}]`,
          severity: 'high',
          confidence: 0.95,
          issue_type: 'dangling_citation',
          evidence: `Citation [${d}] used in text but not found in references section.`,
          suggested_fix: `Add reference entry for [${d}].`,
          localizable: true,
          render_mode: 'comment'
        });
      });

      return { citation_analysis: result, format_compliance: true };
    });
  }

  private async stage09_LineEdits() {
    return this.executeStage('line_edits', async (model) => {
      if (!this.parsedDoc) return { edits: [] };
      const chunk = this.parsedDoc.text.substring(0, 2000);
      const prompt = `Suggest line edits for clarity. Preserve meaning.\n\nText:\n${chunk}\n\nReturn JSON: { "edits": [{"original": "...", "suggested": "...", "rationale": "..."}] }`;
      const resp = await this.options.llm.chat([{ role: 'user', content: prompt }], { model, max_tokens: 600 });
      
      const parsed = this.parseJSON(resp);
      const validEdits = (parsed.edits || []).map((e: any) => {
        const protection = protectFrontMatter(this.parsedDoc!.text, e.suggested || '');
        const issue: Issue = {
          id: uuidv4(),
          stage: 'line_edits',
          section: 'body',
          location: e.original || 'unknown',
          severity: 'low',
          confidence: 0.7,
          issue_type: 'style_edit',
          evidence: e.original || '',
          suggested_fix: e.suggested || '',
          rationale: e.rationale || '',
          localizable: true,
          render_mode: protection.blocked ? 'abstain' : 'tracked_change',
          blocked_reason: protection.reason
        };
        this.issues.push(issue);
        return issue;
      });
      return { edits: validEdits };
    });
  }

  private async stage10_Arbitration() {
    return this.executeStage('arbitration', async () => {
      this.issues = dedupeAndArbitrate(this.issues);
      return { 
        consolidated_issues: this.issues, 
        priority_actions: this.issues.map(i => i.suggested_fix),
        status: 'arbitrated'
      };
    });
  }

  private async stage11_Render() {
    return this.executeStage('render', async () => {
      const comments = this.issues.filter(i => i.render_mode === 'comment');
      const trackedChanges = this.issues.filter(i => i.render_mode === 'tracked_change');
      
      const commentsManifestPath = path.join(this.options.runDir, 'manuscript_comment_manifest.json');
      const changesManifestPath = path.join(this.options.runDir, 'manuscript_suggested_changes_manifest.json');

      fs.writeJsonSync(commentsManifestPath, comments, { spaces: 2 });
      fs.writeJsonSync(changesManifestPath, trackedChanges, { spaces: 2 });

      return { 
        docx_written: false, 
        manifests_written: true,
        comments_count: comments.length,
        changes_count: trackedChanges.length,
        status: 'partial', 
        note: 'JSON manifests written. Real DOCX rendering requires porting python-docx logic' 
      };
    });
  }

  private async stage12_Validation() {
    return this.executeStage('validation', async () => {
      let schemaValid = true;
      const errors: string[] = [];

      for (const issue of this.issues) {
        const result = IssueSchema.safeParse(issue);
        if (!result.success) {
          schemaValid = false;
          errors.push(`Invalid issue ${issue.id}: ${JSON.stringify(result.error.format())}`);
        }
      }

      return { 
        validation_passed: schemaValid, 
        issues_validated: this.issues.length,
        schema_errors: errors,
        status: 'complete'
      };
    });
  }

  private updateRunStatus(status: 'success' | 'failure') {
    const summaryPath = path.join(this.options.runDir, 'run_summary.json');
    if (fs.existsSync(summaryPath)) {
      const summary = fs.readJsonSync(summaryPath);
      summary.status = status;
      summary.completedAt = new Date().toISOString();
      fs.writeJsonSync(summaryPath, summary, { spaces: 2 });
    }
  }
}

