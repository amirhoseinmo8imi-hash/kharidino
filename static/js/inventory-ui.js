(function () {
  "use strict";

  /*
   * Compatibility guard for the current storefront.
   *
   * Inventory data is not exposed by the current Flask application, so this
   * script must not probe the non-existent /api/inventory/<id> endpoint.
   * Product availability is therefore rendered from the server-side product
   * and offer data until a dedicated inventory API is added.
   */

  (function suppressLegacyCandidateProbes() {
    var NativeImage = window.Image;
    if (!NativeImage || window.__kharidinoCandidateProbeGuard) return;

    window.__kharidinoCandidateProbeGuard = true;
    window.Image = function () {
      var image = new NativeImage(...arguments);
      var descriptor = Object.getOwnPropertyDescriptor(
        HTMLImageElement.prototype,
        "src"
      );

      if (!descriptor || !descriptor.set || !descriptor.get) return image;

      Object.defineProperty(image, "src", {
        configurable: true,
        enumerable: true,
        get: function () {
          return descriptor.get.call(image);
        },
        set: function (value) {
          var source = String(value || "");
          if (source.indexOf("/google_candidates/no_image_27/") !== -1) {
            return;
          }
          descriptor.set.call(image, value);
        }
      });

      return image;
    };

    window.Image.prototype = NativeImage.prototype;
  })();
})();
