export type RequestGeneration = {
  current: number
}

export function createRequestGeneration(): RequestGeneration {
  return { current: 0 }
}

export function beginRequest(state: RequestGeneration): number {
  state.current += 1
  return state.current
}

export function invalidateRequests(state: RequestGeneration): void {
  state.current += 1
}

export function isCurrentRequest(state: RequestGeneration, generation: number): boolean {
  return state.current === generation
}

export function shouldInvalidateScreenIntent(currentScreen: string, nextScreen: string): boolean {
  return currentScreen !== nextScreen
}
