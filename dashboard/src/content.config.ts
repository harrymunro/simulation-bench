import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const submissions = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/submissions" }),
  schema: z.object({
    id: z.string(),
    runDate: z.string(),
    benchmarkId: z.string(),
    harness: z.string(),
    model: z.string(),
    runTag: z.string().nullable(),
    totalScore: z.number().nullable(),
    categoryScores: z.object({
      conceptual_modelling: z.number().nullable(),
      data_topology: z.number().nullable(),
      simulation_correctness: z.number().nullable(),
      experimental_design: z.number().nullable(),
      results_interpretation: z.number().nullable(),
      code_quality: z.number().nullable(),
      traceability: z.number().nullable(),
    }),
    totalTokens: z.number().nullable(),
    inputTokens: z.number().nullable(),
    outputTokens: z.number().nullable(),
    tokenCountMethod: z.string().nullable(),
    runtimeSeconds: z.number().nullable(),
    interventionCategory: z.string(),
    reviewer: z.string().nullable(),
    reviewDate: z.string().nullable(),
    recommendation: z.string().nullable(),
    notes: z.string().nullable(),
    evaluationReport: z
      .object({
        automatedChecksPassed: z.number().nullable(),
        automatedChecksTotal: z.number().nullable(),
        automatedPassRate: z.number().nullable(),
        behaviouralChecksPassed: z.number().nullable(),
        behaviouralChecksTotal: z.number().nullable(),
        reportRelativePath: z.string(),
        scenarioTotalTonnesMeans: z.record(z.string(), z.number()).nullable(),
      })
      .nullable(),
    files: z.array(
      z.object({
        path: z.string(),
        kind: z.enum(["text", "binary", "download"]),
        bytes: z.number(),
        language: z.string().nullable(),
      })
    ),
  }),
});

const methodology = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/methodology" }),
  schema: z.object({
    title: z.string(),
    sourcePath: z.string().nullable(),
  }),
});

export const collections = { submissions, methodology };
