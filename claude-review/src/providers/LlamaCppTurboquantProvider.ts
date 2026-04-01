import { LlamaCppProvider } from './LlamaCppProvider';
import { ChatMessage, ChatOptions } from './LLMProvider';
import { EventLogger } from '../logging/EventLogger';

export interface TurboChatOptions extends ChatOptions {
  turbo_cache?: 'fp16' | 'q8_0' | 'q4_0' | 'auto';
  turbo_cache_type?: 'key_only' | 'value_only' | 'both';
}

export class LlamaCppTurboquantProvider extends LlamaCppProvider {
  private isTurboVerified: boolean = false;

  constructor(baseURL: string, defaultModel: string, logger: EventLogger) {
    super(baseURL, defaultModel, logger);
  }

  public async verifyTurboSupport(): Promise<boolean> {
    const startTime = Date.now();
    try {
      // Check llama-server capabilities endpoint if it exists
      const response = await fetch(`${(this as any).client.baseURL}/props`);
      if (response.ok) {
        const props = await response.json();
        this.isTurboVerified = !!props.turbo_quant_support;
        (this as any).logger.logNetwork({
          destination: (this as any).client.baseURL,
          purpose: 'capability_check (turboquant)',
          status: 200,
          duration: Date.now() - startTime,
          timestamp: Date.now()
        });
        return this.isTurboVerified;
      }
    } catch (e) {
      // Fail open to standard llama.cpp if check fails
    }
    return false;
  }

  public override async chat(messages: ChatMessage[], options: TurboChatOptions = {}): Promise<string> {
    if (options.turbo_cache && !this.isTurboVerified) {
      console.warn(`[warning] turboquant unavailable or not verified; falling back to llama_cpp_standard`);
    }

    // Pass turbo params to the underlying client via metadata or extraBody if the SDK supports it
    // For now, we assume llama-server-turboquant accepts them in the standard chat completions body
    return super.chat(messages, options);
  }
}
