```v2 of List vs Grid view```

# Idea Evaluation

## Problem/Opportunity

The current grid view design of the room tiles on the property details page within our OTA Booking Engine is both visually overwhelming to users and difficult to read/compare.

## Potential Solution

- Conduct an A/B Test
  - We already have a design that was created a few years ago, but we don't know why we didn't move forward with this and choose the grid view instead (likely due to an overwhelming amount of room types that we were receiving via API from our suppliers which has since been mitigated to some extent, but still far from perfect)
- Use a linear flow, reducing the "memory load" of remembering which grid item had which amenity.
- While readability improves, conversion might drop if users feel the list is endless. A "See More" pagination strategy is required.
- Requires a different implementation on mobile - consider implementing a "sticky" filter bar or grouping rooms by category (e.g., "Suites" vs. "Standard")

## Existing Insights

1. Marriott's property details page uses a list view to compare room types/rates
2. Hick’s Law: the time it takes to make a decision increases logarithmically with the number of choices available
3. Humans use F-shaped scanning patterns to visually digest information, making it easier for users to process text-heavy details (bed type, breakfast inclusion, cancellation policy) without zig-zagging their eyes.
4. Loss of Visual Emotion: Grid views are 20-30% more effective for "lifestyle" or resort properties where the look of the room is the primary selling point over the price/utility.
