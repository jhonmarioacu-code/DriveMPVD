/** Stable explorer contracts that other features may consume. */
export { openFile } from "@/features/explorer/model/file-actions";
export {
  explorerErrorMessage,
  formatFileSize,
  formatModifiedDate,
} from "@/features/explorer/model/formatters";
export type { StorageEntry } from "@/features/explorer/model/types";
