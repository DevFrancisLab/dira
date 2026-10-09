/** Sample locations used when an upload cannot be read. Matches the backend samples. */

export const SAMPLE_ROWS = [
  {
    loc_id: "SAMPLE-01",
    lat: -1.2864,
    lon: 36.8172,
    housing_class: "permanent_masonry",
    tiv_kes: 18500000,
    source: "sample",
  },
  {
    loc_id: "SAMPLE-02",
    lat: -1.3197,
    lon: 36.9256,
    housing_class: "semi_permanent",
    tiv_kes: 3200000,
    source: "sample",
  },
  {
    loc_id: "SAMPLE-03",
    lat: -1.2833,
    lon: 36.7167,
    housing_class: "informal_iron_sheet",
    tiv_kes: 740000,
    source: "sample",
  },
  {
    loc_id: "SAMPLE-04",
    lat: -1.3031,
    lon: 36.89,
    housing_class: "concrete_rcc",
    tiv_kes: 42000000,
    source: "sample",
  },
];

export function sampleIngest(filename) {
  const name = filename || "upload";
  return {
    filename: name,
    kind: "file",
    status: "sample",
    summary: `${name} could not be read as exposure, so sample Nairobi locations are shown.`,
    page: "map",
    rows: SAMPLE_ROWS,
  };
}
