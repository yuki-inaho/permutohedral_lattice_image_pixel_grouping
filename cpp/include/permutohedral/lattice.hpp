/*
    Copyright (c) 2013, Philipp Krähenbühl
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:
        * Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.
        * Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.
        * Neither the name of the Stanford University nor the
        names of its contributors may be used to endorse or promote products
        derived from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY Philipp Krähenbühl ''AS IS'' AND ANY
    EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
    WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL Philipp Krähenbühl BE LIABLE FOR ANY
    DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
    ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
namespace permutohedral::detail {
// Full equality, rather than the hash alone, determines simplex identity.
// The final elevated coordinate is omitted because the coordinates sum to zero.
template <std::size_t D> struct SimplexKey {
    std::array<int, D * (D + 1)> coordinates{};
    bool operator==(const SimplexKey& other) const noexcept {
        return coordinates == other.coordinates;
    }
};

template <std::size_t D> struct KeyHash {
    std::size_t operator()(const SimplexKey<D>& key) const noexcept {
        std::uint64_t h = 1469598103934665603ULL;
        for (int value : key.coordinates) {
            h ^= std::uint32_t(value);
            h *= 1099511628211ULL;
        }
        return std::size_t(h);
    }
};

template <std::size_t D> class SimplexLocator {
    static_assert(D >= 1 && D <= 8, "Supported feature dimension: 1..8");
    static constexpr int d = int(D);
    static constexpr int n = d + 1;
    std::array<double, D> scales_{};

public:
    struct Location {
        std::array<std::array<int, D + 1>, D + 1> vertices{};
        std::array<double, D + 1> weights{};
        std::array<double, D + 1> elevated{};

        SimplexKey<D> key() const {
            // Vertex order does not affect simplex identity.
            auto ordered = vertices;
            std::sort(ordered.begin(), ordered.end());
            SimplexKey<D> result;
            for (int r = 0; r < n; ++r)
                for (int j = 0; j < d; ++j)
                    result.coordinates[r * d + j] = ordered[r][j];
            return result;
        }
    };

    SimplexLocator() {
        // Conventional Adams/Kraehenbuehl filtering scale (with_blur=true).
        // This normalization is retained even though NO filter is applied.
        const double inverse_sigma = std::sqrt(2.0 / 3.0) * n;
        for (int j = 0; j < d; ++j)
            scales_[j] = inverse_sigma / std::sqrt(double((j + 1) * (j + 2)));
    }

    Location locate(const std::array<double, D>& feature) const {
        Location result;
        double sum_feature = 0;
        for (int j = d; j > 0; --j) {
            if (!std::isfinite(feature[j - 1]))
                throw std::invalid_argument("Non-finite input feature.");
            const double scaled = feature[j - 1] * scales_[j - 1];
            result.elevated[j] = sum_feature - j * scaled;
            sum_feature += scaled;
        }
        result.elevated[0] = sum_feature;

        std::array<int, D + 1> remainder{}, rank{};
        int sum_rounded = 0;
        for (int j = 0; j < n; ++j) {
            const double v = result.elevated[j] / n;
            if (!std::isfinite(v) || std::abs(v) > 10000000.0)
                throw std::invalid_argument("Feature too large for safe lattice indexing.");
            const double lower = std::floor(v);
            // Nearest integer; an exact half goes to the lower integer.
            const int rounded = int((v - lower > 0.5) ? lower + 1 : lower);
            remainder[j] = rounded * n;
            sum_rounded += rounded;
        }
        // Stable ranking of residuals selects the enclosing simplex.
        for (int i = 0; i < d; ++i) {
            for (int j = i + 1; j < n; ++j) {
                if (result.elevated[i] - remainder[i] <
                    result.elevated[j] - remainder[j]) ++rank[i];
                else ++rank[j];
            }
        }
        for (int j = 0; j < n; ++j) {
            rank[j] += sum_rounded;
            if (rank[j] < 0) {
                rank[j] += n;
                remainder[j] += n;
            } else if (rank[j] > d) {
                rank[j] -= n;
                remainder[j] -= n;
            }
            if (rank[j] < 0 || rank[j] > d)
                throw std::runtime_error("Invalid simplex rank.");
        }

        std::array<double, D + 2> barycentric{};
        for (int j = 0; j < n; ++j) {
            const double delta = (result.elevated[j] - remainder[j]) / n;
            barycentric[d - rank[j]] += delta;
            barycentric[d - rank[j] + 1] -= delta;
        }
        barycentric[0] += 1.0 + barycentric[n];
        for (int r = 0; r < n; ++r) {
            result.weights[r] = barycentric[r];
            for (int j = 0; j < n; ++j) {
                const int canonical = rank[j] <= d - r ? r : r - n;
                result.vertices[r][j] = remainder[j] + canonical;
            }
        }
        return result;
    }

    std::array<double, D> inverse_elevation(
        const std::array<double, D + 1>& elevated) const {
        // E^T E = inverse_sigma^2 I; used for independent round-trip tests.
        std::array<double, D> result{};
        const double norm_squared = (2.0 / 3.0) * n * n;
        for (int k = 0; k < d; ++k) {
            double value = elevated[0];
            for (int j = 1; j <= k; ++j) value += elevated[j];
            value -= (k + 1) * elevated[k + 1];
            result[k] = scales_[k] * value / norm_squared;
        }
        return result;
    }
};


}  // namespace permutohedral::detail
