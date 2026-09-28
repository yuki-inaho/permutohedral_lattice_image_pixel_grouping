#include "permutohedral/core.hpp"
#include "permutohedral/lattice.hpp"
#include <algorithm>
#include <array>
#include <stdexcept>
#include <type_traits>
#include <unordered_map>

namespace permutohedral {
namespace {
void validate_features(const double* features, std::size_t count, int dimension) {
    if (count == 0 || count > max_pixels || !features)
        throw std::invalid_argument("Features must contain 1..20,000,000 points.");
    if (dimension < 1 || dimension > 8)
        throw std::invalid_argument("Feature dimension must be between 1 and 8.");
}
template<std::size_t D> Partition partition_impl(const double* features, std::size_t count) {
    detail::SimplexLocator<D> locator;
    std::unordered_map<detail::SimplexKey<D>, int, detail::KeyHash<D>> table;
    table.reserve(count / 4 + 64);
    Partition result{Labels(count), 0};
    for (std::size_t i = 0; i < count; ++i) {
        std::array<double, D> feature{};
        std::copy_n(features + i * D, D, feature.begin());
        auto inserted = table.emplace(locator.locate(feature).key(), result.classes);
        if (inserted.second) ++result.classes;
        result.labels[i] = inserted.first->second;
    }
    return result;
}
template<std::size_t D> Geometry geometry_impl(const double* features, std::size_t count) {
    detail::SimplexLocator<D> locator;
    Geometry result;
    result.vertices.reserve(count * (D + 1) * (D + 1));
    result.weights.reserve(count * (D + 1));
    result.elevated.reserve(count * (D + 1));
    for (std::size_t i = 0; i < count; ++i) {
        std::array<double, D> feature{};
        std::copy_n(features + i * D, D, feature.begin());
        const auto found = locator.locate(feature);
        for (const auto& vertex : found.vertices)
            result.vertices.insert(result.vertices.end(), vertex.begin(), vertex.end());
        result.weights.insert(result.weights.end(), found.weights.begin(), found.weights.end());
        result.elevated.insert(result.elevated.end(), found.elevated.begin(), found.elevated.end());
    }
    return result;
}
// One dispatch implementation is shared by partitioning and geometry inspection.
template<class Operation> auto dispatch(int dimension, Operation&& operation) {
    switch (dimension) {
        case 1: return operation(std::integral_constant<std::size_t, 1>{});
        case 2: return operation(std::integral_constant<std::size_t, 2>{});
        case 3: return operation(std::integral_constant<std::size_t, 3>{});
        case 4: return operation(std::integral_constant<std::size_t, 4>{});
        case 5: return operation(std::integral_constant<std::size_t, 5>{});
        case 6: return operation(std::integral_constant<std::size_t, 6>{});
        case 7: return operation(std::integral_constant<std::size_t, 7>{});
        case 8: return operation(std::integral_constant<std::size_t, 8>{});
        default: throw std::invalid_argument("Feature dimension must be between 1 and 8.");
    }
}
}  // namespace
Partition label_features(const double* features, std::size_t count, int dimension) {
    validate_features(features, count, dimension);
    return dispatch(dimension, [&](auto d) { return partition_impl<decltype(d)::value>(features, count); });
}
Geometry locate_simplices(const double* features, std::size_t count, int dimension) {
    validate_features(features, count, dimension);
    if (count > 100'000) throw std::invalid_argument("Geometry inspection is limited to 100,000 points.");
    return dispatch(dimension, [&](auto d) { return geometry_impl<decltype(d)::value>(features, count); });
}
}  // namespace permutohedral
