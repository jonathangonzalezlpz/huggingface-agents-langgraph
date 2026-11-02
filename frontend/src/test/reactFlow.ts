import { vi } from 'vitest';

/**
 * jsdom has no layout engine. React Flow needs a ResizeObserver, a DOMMatrix and element
 * sizes to render; these stand-ins follow the library's own testing guidance.
 */
export function installReactFlowMocks(): void {
  class ResizeObserverStub {
    constructor(private readonly callback: ResizeObserverCallback) {}
    observe(target: Element) {
      const size = { width: 1200, height: 800 };
      const entry = {
        target,
        contentRect: {
          ...size,
          x: 0,
          y: 0,
          top: 0,
          left: 0,
          right: size.width,
          bottom: size.height,
        },
        borderBoxSize: [{ inlineSize: size.width, blockSize: size.height }],
        contentBoxSize: [{ inlineSize: size.width, blockSize: size.height }],
      };
      this.callback([entry as unknown as ResizeObserverEntry], this as unknown as ResizeObserver);
    }
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', ResizeObserverStub);

  class DOMMatrixReadOnlyStub {
    m22: number;
    constructor(transform?: string) {
      const scale = transform?.match(/scale\(([\d.]+)\)/)?.[1];
      this.m22 = scale === undefined ? 1 : Number(scale);
    }
  }
  vi.stubGlobal('DOMMatrixReadOnly', DOMMatrixReadOnlyStub);

  Object.defineProperties(HTMLElement.prototype, {
    offsetHeight: {
      configurable: true,
      get() {
        return parseFloat((this as HTMLElement).style.height) || 800;
      },
    },
    offsetWidth: {
      configurable: true,
      get() {
        return parseFloat((this as HTMLElement).style.width) || 1200;
      },
    },
  });
  (SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
    ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect;
}
