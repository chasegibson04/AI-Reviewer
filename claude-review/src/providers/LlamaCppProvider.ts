import { LLMProvider, ChatMessage, ChatOptions } from './LLMProvider';
import { EventLogger } from '../logging/EventLogger';

export class LlamaCppProvider extends LLMProvider {
  constructor(baseURL: string, defaultModel: string, logger: EventLogger) {
    // llama.cpp server usually doesn't require an API key, so we pass 'no-key'
    super('no-key', baseURL, defaultModel, logger);
  }

  public override async chat(messages: ChatMessage[], options: ChatOptions = {}): Promise<string> {
    const startTime = Date.now();
    const model = options.model || (this as any).defaultModel;
    
    // Logic to verify llama-server reachability
    try {
      return await super.chat(messages, options);
    } catch (error: any) {
      this.handleLlamaError(error);
      throw error;
    }
  }

  protected handleLlamaError(error: any) {
    if (error.status === 404) {
      console.warn(`[backend] llama.cpp | endpoint not found. Ensure llama-server is running with --api.`);
    }
  }
}
