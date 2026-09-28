// Test-only C ABI for environments unable to download nanobind.
// This is NOT the production Python binding and is never installed in a wheel.
#include "permutohedral/core.hpp"
#include <algorithm>
#include <exception>
#include <string>

namespace {
thread_local std::string error_message;
template<class F> int guarded(F function) noexcept {
    try { function(); error_message.clear(); return 0; }
    catch (const std::exception& error) { error_message = error.what(); return 1; }
    catch (...) { error_message = "Unknown C++ exception"; return 2; }
}
}
extern "C" {
const char* ps_error() noexcept { return error_message.c_str(); }
int ps_label(const double* features, std::size_t count, int dimension,
             std::int32_t* output, int* classes) noexcept {
    return guarded([&] {
        const auto result = permutohedral::label_features(features, count, dimension);
        std::copy(result.labels.begin(), result.labels.end(), output);
        *classes = result.classes;
    });
}
int ps_geometry(const double* features, std::size_t count, int dimension,
                std::int32_t* vertices, double* weights, double* elevated) noexcept {
    return guarded([&] {
        const auto result = permutohedral::locate_simplices(features, count, dimension);
        std::copy(result.vertices.begin(), result.vertices.end(), vertices);
        std::copy(result.weights.begin(), result.weights.end(), weights);
        std::copy(result.elevated.begin(), result.elevated.end(), elevated);
    });
}
int ps_components(const std::int32_t* labels, int width, int height,
                  std::int32_t* output, int* classes) noexcept {
    return guarded([&] {
        const auto result = permutohedral::connected_components(labels, width, height);
        std::copy(result.labels.begin(), result.labels.end(), output);
        *classes = result.classes;
    });
}
int ps_merge(const std::uint8_t* rgb, const std::int32_t* labels, int width, int height,
             int target, double compactness, double sigma,
             std::int32_t* output, int* classes, int* components) noexcept {
    return guarded([&] {
        const auto result = permutohedral::merge_regions({width, height, rgb}, labels,
                                                        target, compactness, sigma);
        std::copy(result.output.labels.begin(), result.output.labels.end(), output);
        *classes = result.output.classes;
        *components = result.initial_components;
    });
}
}
