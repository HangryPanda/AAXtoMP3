/**
 * MSW server setup for Node.js test environment
 */

import { setupServer } from "msw/node";
import { handlers } from "./handlers";

// Create the server with all handlers
export const server = setupServer(...handlers);
