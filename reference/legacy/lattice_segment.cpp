/*
 * Permutohedral simplex partition and optional connected-region agglomeration.
 * C++17, libpng. No SLIC, k-means, neural model, or image-generation model.
 * The simplex-location routine is adapted from the scalar implementation in
 * the user-supplied probreg/third_party/permutohedral/permutohedral.cpp.
 * Original algorithm: Adams, Baek and Davis, Eurographics 2010.
 * Adaptations: double precision, full simplex keys, image I/O, connected-region
 * merging, rendering and validation. Original third-party notice follows.
 */
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
#include <png.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <queue>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
using Labels = std::vector<int>;

struct Image {
    int width = 0, height = 0;
    std::vector<std::uint8_t> rgb;
    int size() const { return width * height; }
};

Image read_png(const fs::path& path) {
    png_image png{};
    png.version = PNG_IMAGE_VERSION;
    if (!png_image_begin_read_from_file(&png, path.string().c_str())) {
        const std::string message = png.message;
        png_image_free(&png);
        throw std::runtime_error("PNG read failed: " + message);
    }
    const std::uint64_t count = std::uint64_t(png.width) * png.height;
    if (count == 0 || count > 20000000ULL) {
        png_image_free(&png);
        throw std::runtime_error("Image must contain 1..20,000,000 pixels.");
    }
    png.format = PNG_FORMAT_RGB;
    Image image{int(png.width), int(png.height), {}};
    image.rgb.resize(std::size_t(count) * 3);
    // Explicit white background for an alpha-bearing input.
    png_color background{255, 255, 255};
    if (!png_image_finish_read(&png, &background, image.rgb.data(), 0, nullptr)) {
        const std::string message = png.message;
        png_image_free(&png);
        throw std::runtime_error("PNG decode failed: " + message);
    }
    png_image_free(&png);
    return image;
}

void write_png(const fs::path& path, const Image& image) {
    png_image png{};
    png.version = PNG_IMAGE_VERSION;
    png.width = png_uint_32(image.width);
    png.height = png_uint_32(image.height);
    png.format = PNG_FORMAT_RGB;
    if (!png_image_write_to_file(&png, path.string().c_str(), 0,
                                  image.rgb.data(), 0, nullptr)) {
        const std::string message = png.message;
        png_image_free(&png);
        throw std::runtime_error("PNG write failed: " + message);
    }
    png_image_free(&png);
}

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
                throw std::runtime_error("Non-finite input feature.");
            const double scaled = feature[j - 1] * scales_[j - 1];
            result.elevated[j] = sum_feature - j * scaled;
            sum_feature += scaled;
        }
        result.elevated[0] = sum_feature;

        std::array<int, D + 1> remainder{}, rank{};
        int sum_rounded = 0;
        for (int j = 0; j < n; ++j) {
            const double v = result.elevated[j] / n;
            if (std::abs(v) > 10000000.0)
                throw std::runtime_error("Feature too large for safe lattice indexing.");
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

struct Partition {
    Labels labels;
    int classes = 0;
};

template <std::size_t D, typename FeatureProvider>
Partition partition(int pixels, FeatureProvider feature) {
    SimplexLocator<D> locator;
    std::unordered_map<SimplexKey<D>, int, KeyHash<D>> table;
    table.reserve(std::size_t(pixels) / 4 + 64);
    Partition result{Labels(pixels), 0};
    for (int i = 0; i < pixels; ++i) {
        const auto key = locator.locate(feature(i)).key();
        const auto inserted = table.emplace(key, result.classes);
        if (inserted.second) ++result.classes;
        result.labels[i] = inserted.first->second;
    }
    return result;
}

Partition connected_components(const Labels& labels, int width, int height) {
    const int pixels = width * height;
    Partition result{Labels(pixels, -1), 0};
    std::vector<int> queue;
    queue.reserve(pixels);
    for (int seed = 0; seed < pixels; ++seed) {
        if (result.labels[seed] >= 0) continue;
        queue.clear();
        queue.push_back(seed);
        result.labels[seed] = result.classes;
        for (std::size_t head = 0; head < queue.size(); ++head) {
            const int p = queue[head], x = p % width, y = p / width;
            const std::array<int, 4> neighbours{
                x > 0 ? p - 1 : -1, x + 1 < width ? p + 1 : -1,
                y > 0 ? p - width : -1, y + 1 < height ? p + width : -1};
            for (int q : neighbours) {
                if (q >= 0 && result.labels[q] < 0 && labels[q] == labels[p]) {
                    result.labels[q] = result.classes;
                    queue.push_back(q);
                }
            }
        }
        ++result.classes;
    }
    return result;
}

// Optional, EXPLICIT postprocessing; not part of the lattice construction.
// Merge only spatially adjacent 4-connected components with Ward's SSE cost.
class ConnectedAgglomerator {
    struct Node {
        int parent = -1, pixels = 0;
        std::uint64_t version = 0;
        std::array<double, 5> sum{};
        std::unordered_set<int> adjacent;
    };
    struct Edge {
        double cost;
        int a, b;
        std::uint64_t version_a, version_b;
        bool operator>(const Edge& other) const {
            if (cost != other.cost) return cost > other.cost;
            if (a != other.a) return a > other.a;
            return b > other.b;
        }
    };
    std::vector<Node> nodes_;
    std::priority_queue<Edge, std::vector<Edge>, std::greater<Edge>> heap_;

    double cost(int a, int b) const {
        const Node& x = nodes_[a];
        const Node& y = nodes_[b];
        double squared_distance = 0;
        for (int j = 0; j < 5; ++j) {
            const double delta = x.sum[j] / x.pixels - y.sum[j] / y.pixels;
            squared_distance += delta * delta;
        }
        return (double(x.pixels) * y.pixels / (x.pixels + y.pixels)) *
               squared_distance;
    }
    void push(int a, int b) {
        if (a > b) std::swap(a, b);
        heap_.push({cost(a, b), a, b, nodes_[a].version, nodes_[b].version});
    }
    int root(int i) {
        int r = i;
        while (nodes_[r].parent != r) r = nodes_[r].parent;
        while (i != r) {
            const int next = nodes_[i].parent;
            nodes_[i].parent = r;
            i = next;
        }
        return r;
    }

public:
    Partition merge(const Image& image, const Partition& components,
                    int target, double compactness, double color_sigma) {
        if (target < 1 || target > components.classes)
            throw std::runtime_error("Target must be between 1 and the initial component count.");
        nodes_.resize(components.classes);
        for (int i = 0; i < components.classes; ++i) nodes_[i].parent = i;
        const double spacing = std::sqrt(double(image.size()) / target);
        for (int p = 0; p < image.size(); ++p) {
            const int label = components.labels[p];
            Node& node = nodes_[label];
            ++node.pixels;
            for (int c = 0; c < 3; ++c)
                node.sum[c] += image.rgb[p * 3 + c] / color_sigma;
            node.sum[3] += compactness * (p % image.width + 0.5) / spacing;
            node.sum[4] += compactness * (p / image.width + 0.5) / spacing;
            const int x = p % image.width, y = p / image.width;
            const std::array<int, 2> neighbours{
                x + 1 < image.width ? p + 1 : -1,
                y + 1 < image.height ? p + image.width : -1};
            for (int q : neighbours) {
                if (q >= 0 && components.labels[q] != label) {
                    const int other = components.labels[q];
                    node.adjacent.insert(other);
                    nodes_[other].adjacent.insert(label);
                }
            }
        }
        for (int a = 0; a < components.classes; ++a)
            for (int b : nodes_[a].adjacent) if (a < b) push(a, b);
        int count = components.classes;
        while (count > target) {
            if (heap_.empty()) throw std::runtime_error("Region adjacency graph unexpectedly disconnected.");
            const Edge edge = heap_.top();
            heap_.pop();
            int a = edge.a, b = edge.b;
            if (nodes_[a].parent != a || nodes_[b].parent != b ||
                nodes_[a].version != edge.version_a ||
                nodes_[b].version != edge.version_b ||
                !nodes_[a].adjacent.count(b)) continue;
            // Prefer the larger adjacency set as the surviving storage object.
            if (nodes_[a].adjacent.size() < nodes_[b].adjacent.size()) std::swap(a, b);
            Node& keep = nodes_[a];
            Node& remove = nodes_[b];
            keep.pixels += remove.pixels;
            for (int j = 0; j < 5; ++j) keep.sum[j] += remove.sum[j];
            ++keep.version;
            remove.parent = a;
            keep.adjacent.erase(b);
            for (int neighbour : remove.adjacent) {
                if (neighbour == a) continue;
                nodes_[neighbour].adjacent.erase(b);
                nodes_[neighbour].adjacent.insert(a);
                keep.adjacent.insert(neighbour);
            }
            remove.adjacent.clear();
            for (int neighbour : keep.adjacent) push(a, neighbour);
            --count;
        }
        Partition result{Labels(image.size()), 0};
        Labels dense(nodes_.size(), -1);
        for (int p = 0; p < image.size(); ++p) {
            const int r = root(components.labels[p]);
            if (dense[r] < 0) dense[r] = result.classes++;
            result.labels[p] = dense[r];
        }
        if (result.classes != target) throw std::runtime_error("Incorrect merged region count.");
        return result;
    }
};

std::array<std::uint8_t, 3> label_color(int label) {
    // Fixed seed and deterministic label-only colors; never used in segmentation.
    std::uint64_t z = std::uint64_t(label) + 0x9e3779b97f4a7c15ULL + 20260927;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    z ^= z >> 31;
    return {std::uint8_t(40 + (z & 255) * 200 / 255),
            std::uint8_t(40 + ((z >> 8) & 255) * 200 / 255),
            std::uint8_t(40 + ((z >> 16) & 255) * 200 / 255)};
}

void write_outputs(const fs::path& prefix, const Image& input,
                   const Partition& result) {
    const int classes = result.classes;
    std::vector<std::array<double, 3>> sum(classes);
    std::vector<int> count(classes);
    for (int p = 0; p < input.size(); ++p) {
        const int label = result.labels[p];
        ++count[label];
        for (int c = 0; c < 3; ++c) sum[label][c] += input.rgb[3 * p + c];
    }
    Image colors = input, mean = input, overlay = input, mean_boundaries = input;
    std::vector<std::array<std::uint8_t, 3>> palette(classes), average(classes);
    for (int label = 0; label < classes; ++label) {
        if (!count[label]) throw std::runtime_error("Empty output class.");
        palette[label] = label_color(label);
        for (int c = 0; c < 3; ++c)
            average[label][c] = std::uint8_t(std::lround(sum[label][c] / count[label]));
    }
    for (int p = 0; p < input.size(); ++p) {
        const int x = p % input.width, y = p / input.width;
        const int label = result.labels[p];
        // One-sided raster boundary: one-pixel-width horizontal/vertical edges.
        const bool boundary =
            (x + 1 < input.width && label != result.labels[p + 1]) ||
            (y + 1 < input.height && label != result.labels[p + input.width]);
        for (int c = 0; c < 3; ++c) {
            colors.rgb[3 * p + c] = palette[label][c];
            mean.rgb[3 * p + c] = average[label][c];
            if (boundary) overlay.rgb[3 * p + c] = 0;
            mean_boundaries.rgb[3 * p + c] = boundary ? 0 : average[label][c];
        }
    }
    write_png(prefix.string() + "_regions.png", colors);
    write_png(prefix.string() + "_mean.png", mean);
    write_png(prefix.string() + "_overlay.png", overlay);
    write_png(prefix.string() + "_mean_boundaries.png", mean_boundaries);
    std::ofstream labels(prefix.string() + "_labels.u32", std::ios::binary);
    if (!labels) throw std::runtime_error("Cannot open label output.");
    // Explicit row-major little-endian uint32; zero-based labels.
    for (int label : result.labels) {
        for (int b = 0; b < 4; ++b)
            labels.put(char((std::uint32_t(label) >> (b * 8)) & 255));
    }
    if (!labels) throw std::runtime_error("Failed writing labels.");
}

template <std::size_t D> double test_locator() {
    SimplexLocator<D> locator;
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

struct Options {
    fs::path input, output;
    std::string mode = "xy";
    double spatial_scale = 0.025, color_scale = 0.01;
    double compactness = 0.3, merge_color_sigma = 48;
    int target = 0;
};

void usage() {
    std::cout << "Usage: lattice_segment --input input.png --out result/prefix\n"
              << "  [--mode xy|rgb|xyrgb] [--spatial-scale 0.025] [--color-scale 0.01]\n"
              << "  [--target 0] [--compactness 0.3] [--merge-color-sigma 48]\n"
              << "  --target 0: direct enclosing-simplex labels, no merging.\n"
              << "  --target K: split into 4-connected components, then adjacency-only\n"
              << "              Ward merging to K connected regions.\n"
              << "  --self-test: geometric tests in 2D, 3D and 5D.\n"
              << "Coordinates are pixel centers (x+0.5,y+0.5), RGB values are 0..255.\n";
}

double numeric(const std::string& value) {
    std::size_t parsed = 0;
    const double result = std::stod(value, &parsed);
    if (parsed != value.size() || !std::isfinite(result))
        throw std::runtime_error("Invalid number: " + value);
    return result;
}

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") {
            std::cout << "D=2: 10000 tests passed; max reconstruction error=" << test_locator<2>() << '\n';
            std::cout << "D=3: 10000 tests passed; max reconstruction error=" << test_locator<3>() << '\n';
            std::cout << "D=5: 10000 tests passed; max reconstruction error=" << test_locator<5>() << '\n';
            return 0;
        }
        Options options;
        for (int a = 1; a < argc; ++a) {
            const std::string name = argv[a];
            if (name == "--help" || name == "-h") { usage(); return 0; }
            if (a + 1 == argc) throw std::runtime_error("Missing value for " + name);
            const std::string value = argv[++a];
            if (name == "--input") options.input = value;
            else if (name == "--out") options.output = value;
            else if (name == "--mode") options.mode = value;
            else if (name == "--spatial-scale") options.spatial_scale = numeric(value);
            else if (name == "--color-scale") options.color_scale = numeric(value);
            else if (name == "--compactness") options.compactness = numeric(value);
            else if (name == "--merge-color-sigma") options.merge_color_sigma = numeric(value);
            else if (name == "--target") {
                const double target = numeric(value);
                if (target < 0 || target > 20000000 || std::floor(target) != target)
                    throw std::runtime_error("Target must be an integer in 0..20000000.");
                options.target = int(target);
            } else throw std::runtime_error("Unknown option: " + name);
        }
        if (options.input.empty() || options.output.empty()) {
            usage();
            throw std::runtime_error("--input and --out are required.");
        }
        if (options.spatial_scale <= 0 || options.color_scale <= 0 ||
            options.compactness < 0 || options.merge_color_sigma <= 0)
            throw std::runtime_error("Scales and color sigma must be positive; compactness nonnegative.");
        if (options.mode != "xy" && options.mode != "rgb" && options.mode != "xyrgb")
            throw std::runtime_error("Mode must be xy, rgb, or xyrgb.");
        const Image image = read_png(options.input);
        if (options.output.has_parent_path()) fs::create_directories(options.output.parent_path());
        const auto t0 = Clock::now();
        Partition raw;
        if (options.mode == "xy") {
            raw = partition<2>(image.size(), [&](int p) {
                return std::array<double, 2>{options.spatial_scale * (p % image.width + 0.5),
                                             options.spatial_scale * (p / image.width + 0.5)};
            });
        } else if (options.mode == "rgb") {
            raw = partition<3>(image.size(), [&](int p) {
                return std::array<double, 3>{options.color_scale * image.rgb[3 * p],
                                             options.color_scale * image.rgb[3 * p + 1],
                                             options.color_scale * image.rgb[3 * p + 2]};
            });
        } else {
            raw = partition<5>(image.size(), [&](int p) {
                return std::array<double, 5>{options.spatial_scale * (p % image.width + 0.5),
                                             options.spatial_scale * (p / image.width + 0.5),
                                             options.color_scale * image.rgb[3 * p],
                                             options.color_scale * image.rgb[3 * p + 1],
                                             options.color_scale * image.rgb[3 * p + 2]};
            });
        }
        const auto t1 = Clock::now();
        const Partition components = connected_components(raw.labels, image.width, image.height);
        const auto t2 = Clock::now();
        Partition result = raw;
        if (options.target > 0) {
            ConnectedAgglomerator merger;
            result = merger.merge(image, components, options.target, options.compactness,
                                  options.merge_color_sigma);
        }
        const auto t3 = Clock::now();
        const int final_connected = connected_components(result.labels, image.width, image.height).classes;
        if (options.target > 0 && final_connected != result.classes)
            throw std::runtime_error("Output connectivity verification failed.");
        write_outputs(options.output, image, result);
        const auto milliseconds = [](auto a, auto b) {
            return std::chrono::duration<double, std::milli>(b - a).count();
        };
        std::ostringstream json;
        json << std::setprecision(10)
             << "{\n  \"width\": " << image.width << ",\n  \"height\": " << image.height
             << ",\n  \"mode\": \"" << options.mode
             << "\",\n  \"spatial_scale\": " << options.spatial_scale
             << ",\n  \"color_scale\": " << options.color_scale
             << ",\n  \"coordinate_convention\": \"pixel centers x+0.5,y+0.5; RGB 0..255\""
             << ",\n  \"lattice_normalization\": \"sqrt(2/3)*(D+1)\""
             << ",\n  \"unique_simplex_ids\": " << raw.classes
             << ",\n  \"raw_connected_components\": " << components.classes
             << ",\n  \"target\": " << options.target
             << ",\n  \"compactness\": " << options.compactness
             << ",\n  \"merge_color_sigma\": " << options.merge_color_sigma
             << ",\n  \"output_labels\": " << result.classes
             << ",\n  \"output_connected_components\": " << final_connected
             << ",\n  \"partition_ms\": " << milliseconds(t0, t1)
             << ",\n  \"component_split_ms\": " << milliseconds(t1, t2)
             << ",\n  \"postprocessing_ms\": " << milliseconds(t2, t3)
             << ",\n  \"core_total_ms\": " << milliseconds(t0, t3)
             << ",\n  \"timing_excludes\": \"input/output, rendering, final connectivity verification\""
             << ",\n  \"label_format\": \"row-major little-endian uint32, zero-based\"\n}\n";
        std::ofstream metadata(options.output.string() + ".json");
        metadata << json.str();
        if (!metadata) throw std::runtime_error("Failed writing metadata.");
        std::cout << json.str();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Error: " << error.what() << '\n';
        return 1;
    }
}
