// Connected-component splitting and adjacency-constrained Ward merging.
#include "permutohedral/core.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <functional>
#include <queue>
#include <stdexcept>
#include <unordered_set>

namespace permutohedral {
void validate_shape(std::size_t width, std::size_t height) {
    if (width == 0 || height == 0 || width > max_pixels || height > max_pixels / width)
        throw std::invalid_argument("Image must contain 1..20,000,000 pixels.");
}
Partition connected_components(const Label* labels, int width, int height) {
    validate_shape(width, height);
    if (!labels) throw std::invalid_argument("Null labels buffer.");
    const int pixels = width * height;
    for (int p = 0; p < pixels; ++p)
        if (labels[p] < 0) throw std::invalid_argument("Labels must be nonnegative.");
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
    Partition merge(const ImageView& image, const Partition& components,
                    int target, double compactness, double color_sigma) {
        if (target < 1 || target > components.classes)
            throw std::invalid_argument("Target must be between 1 and the initial component count.");
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


MergeResult merge_regions(ImageView image, const Label* labels, int target,
                         double compactness, double color_sigma) {
    if (image.width < 1 || image.height < 1 || !image.rgb)
        throw std::invalid_argument("Invalid RGB image buffer.");
    validate_shape(image.width, image.height);
    if (!std::isfinite(compactness) || compactness < 0 || compactness > 1e6)
        throw std::invalid_argument("Compactness must be finite and within [0, 1e6].");
    if (!std::isfinite(color_sigma) || color_sigma < 1e-6 || color_sigma > 1e6)
        throw std::invalid_argument("Color sigma must be finite and within [1e-6, 1e6].");
    const auto components = connected_components(labels, image.width, image.height);
    ConnectedAgglomerator merger;
    return {merger.merge(image, components, target, compactness, color_sigma), components.classes};
}
}  // namespace permutohedral
