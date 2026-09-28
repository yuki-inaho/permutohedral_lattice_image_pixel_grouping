#include "permutohedral/core.hpp"
#include "permutohedral/lattice.hpp"
#include <array>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>
template <std::size_t D> double test_locator() {
    permutohedral::detail::SimplexLocator<D> locator;
    std::mt19937 generator(101 + unsigned(D));
    std::uniform_real_distribution<double> uniform(-100, 100);
    double max_error = 0;
    for (int sample = 0; sample < 10000; ++sample) {
        std::array<double, D> feature{};
        for (double& v : feature) v = uniform(generator);
        const auto found = locator.locate(feature);
        const double weight_sum = std::accumulate(found.weights.begin(), found.weights.end(), 0.0);
        if (std::abs(weight_sum - 1) > 1e-9) throw std::runtime_error("Barycentric sum test failed.");
        for (double weight : found.weights)
            if (weight < -1e-9 || weight > 1 + 1e-9)
                throw std::runtime_error("Enclosing-simplex test failed.");
        std::array<double, D + 1> centroid{};
        for (std::size_t r = 0; r <= D; ++r) {
            if (std::accumulate(found.vertices[r].begin(), found.vertices[r].end(), 0) != 0)
                throw std::runtime_error("Hyperplane test failed.");
            for (std::size_t j = 0; j <= D; ++j)
                centroid[j] += double(found.vertices[r][j]) / (D + 1);
        }
        for (std::size_t j = 0; j <= D; ++j) {
            double reconstructed = 0;
            for (std::size_t r = 0; r <= D; ++r)
                reconstructed += found.weights[r] * found.vertices[r][j];
            max_error = std::max(max_error, std::abs(reconstructed - found.elevated[j]));
        }
        if (max_error > 1e-8) throw std::runtime_error("Barycentric reconstruction test failed.");
        const auto round_trip = locator.inverse_elevation(found.elevated);
        for (std::size_t j = 0; j < D; ++j)
            if (std::abs(round_trip[j] - feature[j]) > 1e-8)
                throw std::runtime_error("Elevation round-trip test failed.");
        if (!(locator.locate(locator.inverse_elevation(centroid)).key() == found.key()))
            throw std::runtime_error("Simplex identity test failed.");
    }
    return max_error;
}


template<class Function> void rejects(Function function) {
    try { function(); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error("Expected std::invalid_argument");
}
int main() {
    try {
        std::cout << "D=1, 10000 points: " << test_locator<1>() << '\n';
        std::cout << "D=2, 10000 points: " << test_locator<2>() << '\n';
        std::cout << "D=3, 10000 points: " << test_locator<3>() << '\n';
        std::cout << "D=4, 10000 points: " << test_locator<4>() << '\n';
        std::cout << "D=5, 10000 points: " << test_locator<5>() << '\n';
        std::cout << "D=6, 10000 points: " << test_locator<6>() << '\n';
        std::cout << "D=7, 10000 points: " << test_locator<7>() << '\n';
        std::cout << "D=8, 10000 points: " << test_locator<8>() << '\n';
        const double points[] = {0.25, 0.125, 0.25, 0.125, 100, 100};
        auto labels = permutohedral::label_features(points, 3, 2);
        if (labels.classes != 2 || labels.labels != permutohedral::Labels{0, 0, 1})
            throw std::runtime_error("Partition identity test failed");
        rejects([&] { permutohedral::label_features(points, 0, 2); });
        rejects([&] { permutohedral::label_features(points, 1, 9); });
        rejects([&] { permutohedral::label_features(nullptr, 1, 2); });
        const double bad[] = {std::numeric_limits<double>::infinity()};
        rejects([&] { permutohedral::label_features(bad, 1, 1); });
        const double huge[] = {1e308, 1e308};
        rejects([&] { permutohedral::label_features(huge, 1, 2); });
        rejects([&] { permutohedral::validate_shape(0, 1); });
        rejects([&] { permutohedral::validate_shape(20'000'000, 2); });
        const permutohedral::Label checker[] = {7, 9, 9, 7};
        auto components = permutohedral::connected_components(checker, 2, 2);
        if (components.classes != 4) throw std::runtime_error("4-connectivity test failed");
        const std::uint8_t rgb[12] = {};
        auto merged = permutohedral::merge_regions({2, 2, rgb}, checker, 1, 0.3, 48);
        if (merged.output.classes != 1 || merged.initial_components != 4)
            throw std::runtime_error("Merge target test failed");
        rejects([&] { permutohedral::merge_regions({2, 2, rgb}, checker, 5, 0.3, 48); });
        rejects([&] { permutohedral::merge_regions({2, 2, rgb}, checker, 1, 0.3, 0); });
        std::cout << "Native validation passed (including 80,000 geometry samples).\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
