import fs from 'fs-extra';
import path from 'path';

export type ReviewStage = 
  | 'ingest' 
  | 'sections' 
  | 'structural' 
  | 'terminology' 
  | 'coherence' 
  | 'methods' 
  | 'figures' 
  | 'citations' 
  | 'journal' 
  | 'line_edits' 
  | 'arbitration' 
  | 'render' 
  | 'validation';

export type ProfileName = 'fast' | 'balanced' | 'max_quality' | 'offline_strict' | 'llama_cpp_standard' | 'llama_cpp_turboquant' | 'llama_cpp_long_context' | 'benchmark_local_matrix';

export interface ProfileConfig {
  default: string;
  stages: Partial<Record<ReviewStage, string>>;
}

export const PROFILES: Record<ProfileName, ProfileConfig> = {
  fast: {
    default: 'qwen2.5:7b-instruct',
    stages: {
      ingest: 'qwen2.5:7b-instruct',
      sections: 'qwen2.5:7b-instruct',
      methods: 'mistral-small3.2:latest',
      arbitration: 'mistral-small3.2:latest'
    }
  },
  balanced: {
    default: 'mistral-small3.2:latest',
    stages: {
      ingest: 'qwen2.5:7b-instruct',
      sections: 'qwen2.5:7b-instruct',
      methods: 'phi4-reasoning:latest',
      arbitration: 'mistral-small3.2:latest'
    }
  },
  max_quality: {
    default: 'mistral-small3.2:latest',
    stages: {
      methods: 'phi4-reasoning:latest',
      arbitration: 'phi4-reasoning:latest',
      line_edits: 'qwen3-coder:30b'
    }
  },
  offline_strict: {
    default: 'qwen3:14b',
    stages: {
      methods: 'qwen3:14b',
      arbitration: 'qwen3:14b'
    }
  },
  llama_cpp_standard: {
    default: 'llama-server-default',
    stages: {
      methods: 'llama-server-default',
      arbitration: 'llama-server-default'
    }
  },
  llama_cpp_turboquant: {
    default: 'llama-server-turbo',
    stages: {
      ingest: 'llama-server-turbo',
      sections: 'llama-server-turbo',
      methods: 'llama-server-turbo',
      arbitration: 'llama-server-turbo'
    }
  },
  llama_cpp_long_context: {
    default: 'llama-server-turbo',
    stages: {
      ingest: 'llama-server-turbo',
      sections: 'llama-server-turbo',
      methods: 'llama-server-turbo',
      arbitration: 'llama-server-turbo'
    }
  },
  benchmark_local_matrix: {
    default: 'qwen2.5-coder:14b',
    stages: {
      methods: 'llama-server-default',
      arbitration: 'llama-server-turbo'
    }
  }
};

export class RoutingService {
  private tracePath: string;
  private trace: any[] = [];
  private profile: ProfileConfig;

  constructor(runDir: string, profileName: ProfileName = 'balanced') {
    this.tracePath = path.join(runDir, 'routing_trace.json');
    this.profile = PROFILES[profileName];
  }

  public getModelForStage(stage: ReviewStage): string {
    const model = this.profile.stages[stage] || this.profile.default;
    this.trace.push({
      stage,
      model,
      timestamp: Date.now()
    });
    this.persistTrace();
    return model;
  }

  private persistTrace() {
    fs.writeJsonSync(this.tracePath, this.trace, { spaces: 2 });
  }
}
