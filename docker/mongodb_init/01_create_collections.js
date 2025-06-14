// Create feeddb database and collections
db = db.getSiblingDB('feeddb');

// Create collections with schema validation
db.createCollection('feed_items', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["fingerprint", "id", "title", "crawled"],
            properties: {
                fingerprint: {
                    bsonType: "string",
                    description: "Feedly fingerprint"
                },
                id: {
                    bsonType: "string",
                    description: "Feedly unique ID"
                },
                language: {
                    bsonType: "string",
                    description: "Content language"
                },
                originId: {
                    bsonType: "string",
                    description: "Original article URL"
                },
                keywords: {
                    bsonType: "array",
                    items: {
                        bsonType: "string"
                    }
                },
                origin: {
                    bsonType: "object",
                    properties: {
                        streamId: { bsonType: "string" },
                        title: { bsonType: "string" },
                        htmlUrl: { bsonType: "string" }
                    }
                },
                content: {
                    bsonType: "object",
                    properties: {
                        content: { bsonType: "string" },
                        direction: { bsonType: "string" }
                    }
                },
                title: {
                    bsonType: "string",
                    description: "Article title"
                },
                published: {
                    bsonType: "long",
                    description: "Publication timestamp"
                },
                crawled: {
                    bsonType: "long",
                    description: "Crawl timestamp"
                },
                author: {
                    bsonType: "string",
                    description: "Article author"
                },
                alternate: {
                    bsonType: "array",
                    items: {
                        bsonType: "object",
                        properties: {
                            href: { bsonType: "string" },
                            type: { bsonType: "string" }
                        }
                    }
                },
                unread: {
                    bsonType: "bool",
                    description: "Unread status"
                },
                categories: {
                    bsonType: "array",
                    items: {
                        bsonType: "object",
                        properties: {
                            id: { bsonType: "string" },
                            label: { bsonType: "string" }
                        }
                    }
                },
                commonTopics: {
                    bsonType: "array",
                    items: {
                        bsonType: "object",
                        properties: {
                            type: { bsonType: "string" },
                            label: { bsonType: "string" },
                            id: { bsonType: "string" },
                            score: { bsonType: ["double", "int"] },
                            salienceLevel: { bsonType: "string" }
                        }
                    }
                },
                featuredMeme: {
                    bsonType: "object",
                    properties: {
                        label: { bsonType: "string" },
                        id: { bsonType: "string" },
                        score: { bsonType: "double" },
                        featured: { bsonType: "bool" }
                    }
                },
                clusters: {
                    bsonType: "array",
                    items: {
                        bsonType: "object",
                        properties: {
                            id: { bsonType: "string" },
                            unread: { bsonType: "bool" }
                        }
                    }
                },
                leoSummary: {
                    bsonType: "object",
                    properties: {
                        sentences: {
                            bsonType: "array",
                            items: { bsonType: "string" }
                        }
                    }
                },
                processing_status: {
                    enum: ["pending", "processed", "filtered_out", "published"],
                    description: "Internal processing status"
                },
                llm_analysis: {
                    bsonType: "object",
                    properties: {
                        relevance_score: { bsonType: "double" },
                        summary: { bsonType: "string" },
                        key_topics: {
                            bsonType: "array",
                            items: { bsonType: "string" }
                        },
                        filtered_reason: { bsonType: ["string", "null"] }
                    }
                }
            }
        }
    }
});

// Create indexes
db.feed_items.createIndex({ "fingerprint": 1 }, { unique: true });
db.feed_items.createIndex({ "id": 1 }, { unique: true });
db.feed_items.createIndex({ "processing_status": 1 });
db.feed_items.createIndex({ "published": 1 });
db.feed_items.createIndex({ "crawled": 1 });
db.feed_items.createIndex({ "keywords": 1 });
db.feed_items.createIndex({ "commonTopics.label": 1 });
db.feed_items.createIndex({ "categories.label": 1 });

// Create a collection for processing metrics
db.createCollection('processing_metrics', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["timestamp", "metric_type", "value"],
            properties: {
                timestamp: {
                    bsonType: "date",
                    description: "When the metric was recorded"
                },
                metric_type: {
                    enum: ["items_ingested", "items_processed", "items_published", "processing_time"],
                    description: "Type of metric"
                },
                value: {
                    bsonType: ["double", "int"],
                    description: "Metric value"
                },
                metadata: {
                    bsonType: "object",
                    description: "Additional metric context"
                }
            }
        }
    }
});

// Create indexes for metrics
db.processing_metrics.createIndex({ "timestamp": 1 });
db.processing_metrics.createIndex({ "metric_type": 1 });

print("Database initialization completed successfully");
