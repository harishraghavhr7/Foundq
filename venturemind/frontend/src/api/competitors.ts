// Thin API client for competitor lookups.
//
// Sections 2–5 lead the backend: there is no /competitors route yet. Until it
// ships, fetchCompetitors serves a representative slice of the startup
// knowledge base (startup_knowledge_base.csv) so the dashboard renders real
// data. When the route exists, replace the stub body with the commented fetch.
import type { Competitor } from "../types";

// A curated subset of startup_knowledge_base.csv — 4 companies per industry.
const KNOWLEDGE_BASE: Competitor[] = [
  // EdTech
  { name: "LearnSphere", industry: "EdTech", country: "United States", website: "https://www.learnsphere.io", description: "An adaptive learning platform that uses AI to personalize K-12 math and science curricula based on each student's pace and gaps." },
  { name: "EduNest", industry: "EdTech", country: "India", website: "https://www.edunest.co", description: "A mobile-first tutoring marketplace connecting students with vetted subject-matter tutors for live one-on-one video sessions." },
  { name: "BrightPath Academy", industry: "EdTech", country: "United Kingdom", website: "https://www.brightpathacademy.com", description: "Offers gamified coding bootcamps for teenagers with project-based curricula and industry mentorship." },
  { name: "SkillForge", industry: "EdTech", country: "Canada", website: "https://www.skillforge.ai", description: "A corporate upskilling platform delivering micro-courses and certifications in cloud computing and data analytics." },

  // FinTech
  { name: "PayPivot", industry: "FinTech", country: "United States", website: "https://www.paypivot.com", description: "A digital wallet enabling instant peer-to-peer payments and bill splitting for young urban professionals." },
  { name: "LendLoom", industry: "FinTech", country: "United Kingdom", website: "https://www.lendloom.io", description: "An AI-driven lending platform that offers small businesses fast credit decisions using alternative data." },
  { name: "NeoBankly", industry: "FinTech", country: "Nigeria", website: "https://www.neobankly.com", description: "A fully digital neobank offering fee-free checking accounts and early salary access to gig workers." },
  { name: "WealthNest", industry: "FinTech", country: "Canada", website: "https://www.wealthnest.io", description: "A robo-advisor delivering automated, goal-based investment portfolios with low management fees." },

  // HealthTech
  { name: "VitalTrack", industry: "HealthTech", country: "United States", website: "https://www.vitaltrack.health", description: "A wearable-integrated platform that monitors chronic disease patients and alerts clinicians to anomalies." },
  { name: "MediQueue", industry: "HealthTech", country: "India", website: "https://www.mediqueue.com", description: "A telemedicine app that reduces wait times by matching patients with available doctors for video consults." },
  { name: "TheraMind", industry: "HealthTech", country: "Canada", website: "https://www.theramind.app", description: "A mental wellness platform connecting users with licensed therapists and offering guided CBT programs." },
  { name: "RadiantAI", industry: "HealthTech", country: "United States", website: "https://www.radiantai.com", description: "Uses deep learning to assist radiologists in detecting tumors and abnormalities in medical imaging scans." },

  // AgriTech
  { name: "FarmSense", industry: "AgriTech", country: "United States", website: "https://www.farmsense.io", description: "Deploys IoT soil sensors and analytics to help farmers optimize irrigation and reduce water usage." },
  { name: "CropMind", industry: "AgriTech", country: "India", website: "https://www.cropmind.ai", description: "Uses satellite imagery and AI to detect crop diseases early and recommend targeted interventions." },
  { name: "AgriLink Market", industry: "AgriTech", country: "Kenya", website: "https://www.agrilinkmarket.com", description: "A digital marketplace connecting smallholder farmers directly with buyers to eliminate middlemen." },
  { name: "LivestockIQ", industry: "AgriTech", country: "Australia", website: "https://www.livestockiq.com", description: "A herd management platform using wearable sensors to monitor cattle health and breeding cycles." },

  // SaaS
  { name: "FlowDesk", industry: "SaaS", country: "United States", website: "https://www.flowdesk.io", description: "A unified project management and collaboration platform with kanban boards, docs, and time tracking." },
  { name: "SyncMail", industry: "SaaS", country: "United Kingdom", website: "https://www.syncmail.com", description: "An email automation and CRM tool helping sales teams manage outreach campaigns and lead pipelines." },
  { name: "DeskHero", industry: "SaaS", country: "Canada", website: "https://www.deskhero.com", description: "An AI-powered customer support helpdesk with ticketing, chatbots, and knowledge base management." },
  { name: "TeamPulse", industry: "SaaS", country: "Australia", website: "https://www.teampulse.app", description: "An employee engagement platform offering anonymous surveys, feedback loops, and wellness tracking." },

  // E-commerce
  { name: "ShopWave", industry: "E-commerce", country: "United States", website: "https://www.shopwave.io", description: "A headless commerce platform enabling brands to build fast, customizable online storefronts." },
  { name: "KartBuddy", industry: "E-commerce", country: "India", website: "https://www.kartbuddy.com", description: "An abandoned cart recovery and personalized recommendation engine for online retailers." },
  { name: "ThriftLoop", industry: "E-commerce", country: "United Kingdom", website: "https://www.thriftloop.com", description: "A peer-to-peer marketplace for buying and selling secondhand fashion and vintage clothing." },
  { name: "FreshCrate", industry: "E-commerce", country: "Australia", website: "https://www.freshcrate.io", description: "An online grocery delivery service specializing in locally sourced organic produce and meal kits." },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Return competitors operating in the given industry.
 * Stubbed against the local knowledge base; swap for the real route when ready.
 */
export async function fetchCompetitors(industry: string): Promise<Competitor[]> {
  // Real implementation (enable once the backend route ships):
  //   const base = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  //   const res = await fetch(`${base}/competitors?industry=${encodeURIComponent(industry)}`);
  //   if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
  //   return res.json();

  await delay(600); // emulate network latency so loading states are observable
  return KNOWLEDGE_BASE.filter((c) => c.industry === industry);
}
