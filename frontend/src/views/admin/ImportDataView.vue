<template>
  <div class="import-view">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t("admin.import.title") }}</span>
          <el-button size="small" :icon="Refresh" @click="refreshAll">{{ t("admin.import.refresh") }}</el-button>
        </div>
      </template>
      <p class="intro">{{ t("admin.import.intro") }}</p>

      <div class="two-col">
        <!-- 左：模板下载 -->
        <div class="panel">
          <h4>{{ t("admin.import.templateTitle") }}</h4>
          <p class="hint">{{ t("admin.import.templateHint") }}</p>
          <el-table :data="templates" size="small" border stripe max-height="320" v-loading="loading.templates">
            <el-table-column prop="category" :label="t('admin.import.category')" width="110" />
            <el-table-column prop="name" :label="t('admin.import.type')" min-width="150" />
            <el-table-column :label="t('admin.import.required')" min-width="150">
              <template #default="{ row }">
                <span class="req">{{ row.required.join("、") }}</span>
              </template>
            </el-table-column>
            <el-table-column width="96" align="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="downloadTemplate(row)">
                  {{ t("admin.import.download") }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 右：上传 -->
        <div class="panel">
          <h4>{{ t("admin.import.uploadTitle") }}</h4>
          <el-form label-width="92px" label-position="left">
            <el-form-item :label="t('admin.import.type')">
              <el-select v-model="form.dataType" filterable class="full" :placeholder="t('admin.import.selectType')">
                <el-option-group v-for="group in groupedTypes" :key="group.category" :label="group.category">
                  <el-option v-for="item in group.items" :key="item.key" :label="item.name" :value="item.key" />
                </el-option-group>
              </el-select>
            </el-form-item>
            <el-form-item :label="t('admin.import.mergeMode')">
              <el-radio-group v-model="form.mergeMode">
                <el-radio value="fill_empty">{{ t("admin.import.modeFill") }}</el-radio>
                <el-radio value="overwrite">{{ t("admin.import.modeOverwrite") }}</el-radio>
              </el-radio-group>
              <div class="hint mode-hint">
                {{ form.mergeMode === "fill_empty" ? t("admin.import.modeFillHint") : t("admin.import.modeOverwriteHint") }}
              </div>
            </el-form-item>
            <el-form-item :label="t('admin.import.file')">
              <el-upload
                :show-file-list="false"
                :before-upload="beforeUpload"
                :http-request="doUpload"
                accept=".xlsx"
              >
                <el-button type="primary" :loading="loading.upload" :disabled="!form.dataType">
                  {{ t("admin.import.chooseFile") }}
                </el-button>
                <span v-if="uploadPercent > 0 && uploadPercent < 100" class="percent">{{ uploadPercent }}%</span>
              </el-upload>
              <div class="hint">{{ t("admin.import.uploadHint") }}</div>
            </el-form-item>
          </el-form>

          <!-- 预览与确认 -->
          <div v-if="currentBatch" class="preview">
            <div class="preview-head">
              <el-tag :type="statusTagType(currentBatch.status)" effect="dark">
                {{ statusLabel(currentBatch.status) }}
              </el-tag>
              <span class="stage">{{ currentBatch.progress?.stage || "" }}</span>
            </div>
            <div v-if="currentBatch.validation?.row_count !== undefined" class="stat-row">
              <span>{{ t("admin.import.rowCount") }}：{{ currentBatch.validation.row_count }}</span>
              <span v-if="preview">· {{ t("admin.import.plannedNodes") }} {{ preview.plan_nodes }}</span>
              <span v-if="preview">· {{ t("admin.import.plannedEdges") }} {{ preview.plan_edges }}</span>
            </div>
            <div v-if="preview" class="stat-row">
              <span class="add">{{ t("admin.import.newNodes") }} {{ preview.new_nodes }}</span>
              <span class="upd">{{ t("admin.import.updatedNodes") }} {{ preview.updated_nodes }}</span>
              <span class="add">{{ t("admin.import.newEdges") }} {{ preview.new_edges }}</span>
              <span class="upd">{{ t("admin.import.updatedEdges") }} {{ preview.updated_edges }}</span>
            </div>
            <el-alert
              v-if="currentBatch.validation?.errors?.length"
              type="error"
              :closable="false"
              :title="t('admin.import.errors')"
            >
              <ul class="msg-list">
                <li v-for="(item, index) in currentBatch.validation.errors.slice(0, 10)" :key="index">
                  {{ item.row ? `${t('admin.import.row')} ${item.row}：` : "" }}{{ item.message }}
                </li>
              </ul>
            </el-alert>
            <el-alert
              v-else-if="currentBatch.validation?.warnings?.length"
              type="warning"
              :closable="false"
              :title="t('admin.import.warnings')"
            >
              <ul class="msg-list">
                <li v-for="(item, index) in currentBatch.validation.warnings.slice(0, 8)" :key="index">
                  {{ item.row ? `${t('admin.import.row')} ${item.row}：` : "" }}{{ item.message }}
                </li>
              </ul>
            </el-alert>
            <div class="actions">
              <el-button
                v-if="currentBatch.status === 'awaiting_confirm'"
                type="primary"
                :loading="loading.action"
                @click="commitBatch"
              >
                {{ t("admin.import.confirm") }}
              </el-button>
              <el-button
                v-if="['awaiting_confirm', 'completed', 'failed'].includes(currentBatch.status)"
                :loading="loading.action"
                @click="rollbackBatch"
              >
                {{ t("admin.import.rollback") }}
              </el-button>
              <span v-if="currentBatch.error_detail" class="error">{{ currentBatch.error_detail }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="hover" class="history-card">
      <template #header>
        <div class="card-header">
          <span>{{ t("admin.import.historyTitle") }}</span>
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            background
            @current-change="loadBatches"
          />
        </div>
      </template>
      <el-table v-loading="loading.batches" :data="batches" size="small" border stripe>
        <el-table-column prop="created_at" :label="t('admin.import.time')" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="data_type_name" :label="t('admin.import.type')" min-width="140" />
        <el-table-column prop="source_filename" :label="t('admin.import.sourceFile')" min-width="160" show-overflow-tooltip />
        <el-table-column :label="t('admin.import.mergeMode')" width="110">
          <template #default="{ row }">
            {{ row.merge_mode === "overwrite" ? t("admin.import.modeOverwrite") : t("admin.import.modeFill") }}
          </template>
        </el-table-column>
        <el-table-column :label="t('admin.import.status')" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('admin.import.result')" min-width="220">
          <template #default="{ row }">
            <span v-if="row.summary?.created_nodes !== undefined">
              +{{ row.summary.created_nodes }} / ~{{ row.summary.updated_nodes }}
              {{ t("admin.import.nodesShort") }} ·
              +{{ row.summary.created_edges ?? 0 }} / ~{{ row.summary.updated_edges ?? 0 }}
              {{ t("admin.import.edgesShort") }}
            </span>
            <span v-else-if="row.summary?.rollback">↩ {{ t("admin.import.rolledBackShort") }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" :label="t('admin.import.operator')" width="110" />
        <el-table-column width="150" align="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showDetail(row)">{{ t("admin.import.detail") }}</el-button>
            <el-button
              v-if="['completed', 'failed'].includes(row.status)"
              link
              type="danger"
              size="small"
              @click="rollbackSpecific(row)"
            >
              {{ t("admin.import.rollback") }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";

const { t } = useI18n();

const templates = ref([]);
const batches = ref([]);
const page = ref(1);
const pageSize = 10;
const total = ref(0);
const uploadPercent = ref(0);
const currentBatch = ref(null);
const loading = reactive({ templates: false, batches: false, upload: false, action: false });

const form = reactive({ dataType: "", mergeMode: "fill_empty" });
const ACTIVE = ["pending", "parsing", "writing", "rolling_back"];
let timer = null;

const groupedTypes = computed(() => {
  const groups = new Map();
  for (const item of templates.value) {
    if (!groups.has(item.category)) groups.set(item.category, { category: item.category, items: [] });
    groups.get(item.category).items.push(item);
  }
  return [...groups.values()];
});

const preview = computed(() => currentBatch.value?.progress?.preview || null);

function statusLabel(status) {
  const map = {
    pending: "statusPending",
    parsing: "statusParsing",
    awaiting_confirm: "statusAwaiting",
    writing: "statusWriting",
    completed: "statusCompleted",
    failed: "statusFailed",
    rolling_back: "statusWriting",
    rolled_back: "statusRolledBack",
  };
  return t(`admin.import.${map[status] || "statusPending"}`);
}

function statusTagType(status) {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "rolled_back") return "info";
  if (status === "awaiting_confirm") return "warning";
  return "primary";
}

function formatTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function failMessage(error, fallbackKey) {
  return error?.response?.data?.detail || t(fallbackKey);
}

async function loadTemplates() {
  loading.templates = true;
  try {
    templates.value = (await api.listImportTemplates()).data || [];
    if (!form.dataType && templates.value.length) form.dataType = templates.value[0].key;
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.loadFailed"));
  } finally {
    loading.templates = false;
  }
}

async function loadBatches() {
  loading.batches = true;
  try {
    const { data } = await api.listImportBatches({ page: page.value, page_size: pageSize });
    batches.value = data.items || [];
    total.value = data.total || 0;
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.loadFailed"));
  } finally {
    loading.batches = false;
  }
}

async function downloadTemplate(row) {
  try {
    const { data } = await api.downloadImportTemplate(row.key);
    const url = window.URL.createObjectURL(new Blob([data]));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${row.name}-导入模板.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.downloadFailed"));
  }
}

function beforeUpload(file) {
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    ElMessage.error(t("admin.import.onlyXlsx"));
    return false;
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error(t("admin.import.fileTooLarge"));
    return false;
  }
  return true;
}

async function doUpload(options) {
  loading.upload = true;
  uploadPercent.value = 0;
  try {
    const formData = new FormData();
    formData.append("file", options.file);
    formData.append("data_type", form.dataType);
    formData.append("merge_mode", form.mergeMode);
    const { data } = await api.uploadImport(formData, (event) => {
      if (event.total) uploadPercent.value = Math.round((event.loaded / event.total) * 100);
    });
    currentBatch.value = data;
    ElMessage.success(t("admin.import.uploadSuccess"));
    options.onSuccess?.(data);
    await loadBatches();
    startPolling(data.id);
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.actionFailed"));
    options.onError?.(error);
  } finally {
    loading.upload = false;
    uploadPercent.value = 0;
  }
}

function startPolling(batchId) {
  stopPolling();
  const tick = async () => {
    try {
      const { data } = await api.getImportBatch(batchId);
      currentBatch.value = data;
      if (ACTIVE.includes(data.status)) {
        timer = setTimeout(tick, 1500);
      } else {
        await loadBatches();
      }
    } catch (error) {
      ElMessage.error(failMessage(error, "admin.import.loadFailed"));
    }
  };
  timer = setTimeout(tick, 800);
}

function stopPolling() {
  if (timer) clearTimeout(timer);
  timer = null;
}

async function commitBatch() {
  loading.action = true;
  try {
    const { data } = await api.commitImport(currentBatch.value.id, { merge_mode: form.mergeMode });
    currentBatch.value = data;
    ElMessage.success(t("admin.import.commitSubmitted"));
    startPolling(data.id);
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.actionFailed"));
  } finally {
    loading.action = false;
  }
}

async function rollbackSpecific(row) {
  try {
    await ElMessageBox.confirm(t("admin.import.rollbackConfirm"), t("admin.import.rollback"), { type: "warning" });
  } catch {
    return;
  }
  loading.action = true;
  try {
    const { data } = await api.rollbackImport(row.id);
    currentBatch.value = data;
    ElMessage.success(t("admin.import.rollbackSubmitted"));
    startPolling(data.id);
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.actionFailed"));
  } finally {
    loading.action = false;
  }
}

function rollbackBatch() {
  return rollbackSpecific(currentBatch.value);
}

async function showDetail(row) {
  try {
    const { data } = await api.getImportBatch(row.id);
    currentBatch.value = data;
    if (ACTIVE.includes(data.status)) startPolling(data.id);
  } catch (error) {
    ElMessage.error(failMessage(error, "admin.import.loadFailed"));
  }
}

async function refreshAll() {
  await Promise.all([loadTemplates(), loadBatches()]);
}

onMounted(async () => {
  await refreshAll();
  const active = batches.value.find((item) => ACTIVE.includes(item.status));
  if (active) {
    currentBatch.value = active;
    startPolling(active.id);
  }
});

onUnmounted(stopPolling);
</script>

<style scoped>
.import-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.intro {
  margin: 0 0 14px;
  color: #5c6b7a;
  font-size: 13px;
  line-height: 1.7;
}
.two-col {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 20px;
}
@media (max-width: 1100px) {
  .two-col {
    grid-template-columns: minmax(0, 1fr);
  }
}
.panel h4 {
  margin: 0 0 6px;
  font-size: 14px;
}
.hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
  margin: 4px 0 10px;
}
.mode-hint {
  flex-basis: 100%;
  margin-top: 2px;
}
.req {
  color: #303133;
}
.full {
  width: 100%;
}
.percent {
  margin-left: 10px;
  color: #409eff;
  font-size: 12px;
}
.preview {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px dashed #dcdfe6;
}
.preview-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stage {
  color: #606266;
  font-size: 12px;
}
.stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin: 10px 0;
  font-size: 13px;
  color: #303133;
}
.add {
  color: #2f855a;
}
.upd {
  color: #b7791f;
}
.msg-list {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.7;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}
.error {
  color: #f56c6c;
  font-size: 12px;
}
.history-card {
  min-height: 240px;
}
.muted {
  color: #c0c4cc;
}
</style>
