import { z } from 'zod';

export const IssueSchema = z.object({
  id: z.string(),
  stage: z.string(),
  section: z.string(),
  location: z.string(),
  severity: z.enum(['low', 'medium', 'high', 'critical']),
  confidence: z.number().min(0).max(1),
  issue_type: z.string(),
  evidence: z.string(),
  suggested_fix: z.string(),
  localizable: z.boolean(),
  render_mode: z.enum(['comment', 'tracked_change', 'abstain', 'report_only']),
  blocked_reason: z.string().optional(),
  source_span: z.string().optional(),
  rationale: z.string().optional(),
  supporting_artifacts: z.array(z.string()).optional()
});

export type Issue = z.infer<typeof IssueSchema>;
