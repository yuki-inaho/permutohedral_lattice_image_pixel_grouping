#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

namespace permutohedral {
using Label = std::int32_t;
using Labels = std::vector<Label>;
inline constexpr std::size_t max_pixels = 20'000'000;

struct Partition { Labels labels; int classes = 0; };
struct Geometry {
    std::vector<std::int32_t> vertices;
    std::vector<double> weights;
    std::vector<double> elevated;
};
struct MergeResult { Partition output; int initial_components = 0; };
struct ImageView {
    int width;
    int height;
    const std::uint8_t* rgb;
    int size() const noexcept { return width * height; }
};

// Buffers are non-owning, row-major, valid for the complete call duration.
// Returned vectors own their memory. All functions are stateless/reentrant.
void validate_shape(std::size_t width, std::size_t height);
Partition label_features(const double* features, std::size_t count, int dimension);
Geometry locate_simplices(const double* features, std::size_t count, int dimension);
Partition connected_components(const Label* labels, int width, int height);
MergeResult merge_regions(ImageView image, const Label* labels, int target,
                         double compactness, double color_sigma);
}  // namespace permutohedral
