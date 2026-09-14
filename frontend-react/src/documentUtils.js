export const statusLabel = status => ({ ready: "Ready to review", failed: "Needs a retry", needs_review: "Check source text", queued: "In queue", processing: "Analyzing" }[status] || "Processing");
