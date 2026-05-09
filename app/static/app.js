const communityPalette = [
  "#2563eb", // 亮蓝
  "#ef4444", // 亮红
  "#10b981", // 翠绿
  "#f59e0b", // 琥珀
  "#8b5cf6", // 紫罗兰
  "#06b6d4", // 靛蓝
  "#f97316", // 橙色
  "#ec4899", // 粉红
];

const scoreWeights = {
  betweenness: 0.34,
  degree: 0.18,
  flow: 0.22,
  delay: 0.14,
  queue: 0.12,
};

const app = Vue.createApp({
  data() {
    return {
      loading: false,
      activePage: "map",
      map: null,
      mapReady: false,
      mapFitted: false,
      renderQueuedAfterZoom: false,
      mapTiles: {
        amap: null,
        satellite: null,
      },
      showFlowAnimation: false,
      showNodeAnnotations: false,
      nodeLayer: null,
      edgeLayer: null,
      selectedCommunityId: null,
      showCrossEdges: true,
      outlierCount: 0,
      outlierNoticeShown: false,
      charts: {},
      detailChart: null,
      meta: {
        availableDates: [],
        availableHours: [],
        datasetBrief: [],
        preprocessing: {},
      },
      studyAreaNetwork: null,
      dashboard: {
        overview: {},
        nodes: [],
        edges: [],
        communities: [],
        communityInsights: [],
        charts: {
          topNodes: [],
          hourlyTrend: [],
          zoneLoad: [],
          communityStats: [],
        },
      },
      filters: {
        date: "",
        hour: 8,
      },
      viewMode: "saturation",
      detailVisible: false,
      selectedNode: null,
      intersectionDetail: {
        connectedSegments: [],
        timeseries: [],
      },
      detailIntersectionId: "",
      detailNavMode: "critical",
      detailSegFilterText: "",
      detailSegCrossOnly: false,
      detailSegHighRiskOnly: false,
      detailSegSortMetric: "vCRatio",
      detailSegSortOrder: "desc",
      // 排行优化：TopN 与搜索（默认显示全部40个）
      rankLimit: 40,
      rankFilter: "",
      rankCommunity: null,
      rankZone: "",
      groupCommunitySortMetric: "avgCriticalScore",
      groupZoneSortMetric: "totalVeh",
      groupSortOrder: "desc",
      selectedRowForRadar: null,
      communityFilterText: "",
      communityCongestionFilter: "",
      communitySortMetric: "avgDelayS",
      communitySortOrder: "desc",
      selectedCommunityRow: null,
      communityZoneFilter: "",
      communityMinSize: 0,
      communityMapOnlyFiltered: false,
      communityPalette: communityPalette,
      // 新增状态
      isAnalyzed: false,
      analyzing: false,
      showImportDialog: false,
      importing: false,
      importFiles: {
        intersections: null,
        road_segments: null,
        hourly_traffic: null,
        segment_daily: null,
      },
    };
  },
  computed: {
    topNodesDisplayed() {
      const all = (this.dashboard.charts && this.dashboard.charts.topNodes) ? this.dashboard.charts.topNodes : [];
      let filtered = all;
      if (this.rankFilter) {
        const kw = String(this.rankFilter).toLowerCase();
        filtered = filtered.filter(
          (n) =>
            String(n.intersection_id).toLowerCase().includes(kw) ||
            String(n.intersection_name || "").toLowerCase().includes(kw)
        );
      }
      if (this.rankCommunity !== null && this.rankCommunity !== undefined) {
        filtered = filtered.filter((n) => Number(n.community_id) === Number(this.rankCommunity));
      }
      if (this.rankZone) {
        filtered = filtered.filter((n) => String(n.functional_zone || "") === String(this.rankZone));
      }
      return filtered.slice(0, Math.max(1, Number(this.rankLimit) || 10));
    },
    communityInsightsDisplayed() {
      const all = this.dashboard && this.dashboard.communityInsights ? this.dashboard.communityInsights : [];
      if (!Array.isArray(all)) return [];
      
      let filtered = all;
      if (this.communityFilterText) {
        const kw = String(this.communityFilterText).toLowerCase();
        filtered = filtered.filter(
          (c) => String(c.communityId).includes(kw) || String(c.dominantZone || "").toLowerCase().includes(kw)
        );
      }
      if (this.communityCongestionFilter) {
        filtered = filtered.filter((c) => String(c.congestionLevel) === String(this.communityCongestionFilter));
      }
      if (this.communityZoneFilter) {
        filtered = filtered.filter((c) => String(c.dominantZone || "") === String(this.communityZoneFilter));
      }
      if (Number(this.communityMinSize) > 0) {
        filtered = filtered.filter((c) => Number(c.size) >= Number(this.communityMinSize));
      }
      const metric = this.communitySortMetric;
      const order = this.communitySortOrder === "asc" ? 1 : -1;
      filtered = filtered.slice().sort((a, b) => (Number(a[metric]) - Number(b[metric])) * order);
      return filtered;
    },
    communityZoneOptions() {
      const rows = this.dashboard && this.dashboard.communityInsights ? this.dashboard.communityInsights : [];
      if (!Array.isArray(rows)) return [];
      return Array.from(new Set(rows.map((r) => r.dominantZone).filter(Boolean))).sort();
    },
    communityAllowedIdSet() {
      const rows = this.communityInsightsDisplayed || [];
      if (!Array.isArray(rows)) return new Set();
      return new Set(rows.map((c) => Number(c.communityId)));
    },
    detailNodeOptions() {
      const nodes = (this.dashboard && this.dashboard.nodes) ? this.dashboard.nodes : [];
      return nodes
        .slice()
        .sort((a, b) => String(a.intersection_id).localeCompare(String(b.intersection_id)))
        .map((n) => ({
          id: n.intersection_id,
          label: `${n.intersection_id} · ${n.intersection_name}`,
        }));
    },
    detailOrderedRows() {
      const rows = (this.dashboard && this.dashboard.charts && this.dashboard.charts.topNodes) ? this.dashboard.charts.topNodes : [];
      if (rows && rows.length) return rows;
      const nodes = (this.dashboard && this.dashboard.nodes) ? this.dashboard.nodes : [];
      return nodes
        .slice()
        .sort((a, b) => Number(b.critical_score) - Number(a.critical_score))
        .map((n, idx) => ({ intersection_id: n.intersection_id, rank: idx + 1 }));
    },
    detailIndex() {
      const id = this.detailIntersectionId || (this.selectedNode ? this.selectedNode.intersection_id : "");
      if (!id) return -1;
      return (this.detailOrderedRows || []).findIndex((r) => r.intersection_id === id);
    },
    detailSegmentsDisplayed() {
      const segments =
        this.intersectionDetail && this.intersectionDetail.connectedSegments
          ? this.intersectionDetail.connectedSegments
          : [];
      let filtered = segments;
      if (this.detailSegFilterText) {
        const kw = String(this.detailSegFilterText).toLowerCase();
        filtered = filtered.filter(
          (s) =>
            String(s.roadName || "").toLowerCase().includes(kw) ||
            String(s.segmentId || "").toLowerCase().includes(kw) ||
            String(s.otherEnd || "").toLowerCase().includes(kw)
        );
      }
      if (this.detailSegCrossOnly) {
        filtered = filtered.filter((s) => Boolean(s.isCrossCommunity));
      }
      if (this.detailSegHighRiskOnly) {
        filtered = filtered.filter((s) => String(s.riskLevel) === "高");
      }
      const metric = this.detailSegSortMetric;
      const order = this.detailSegSortOrder === "asc" ? 1 : -1;
      filtered = filtered
        .slice()
        .sort((a, b) => (Number(a[metric]) - Number(b[metric])) * order);
      return filtered;
    },
    adjacentIntersections() {
      const segments = this.detailSegmentsDisplayed || [];
      const nodeMap = new Map(
        ((this.dashboard && this.dashboard.nodes) ? this.dashboard.nodes : []).map((n) => [n.intersection_id, n])
      );
      const map = new Map();
      segments.forEach((s) => {
        const other = s.otherEnd;
        if (!other) return;
        if (!map.has(other)) {
          const otherNode = nodeMap.get(other);
          map.set(other, {
            intersection_id: other,
            intersection_name: otherNode ? otherNode.intersection_name : "",
            community_id: otherNode ? otherNode.community_id : -1,
            roadNames: new Set(),
            segmentIds: new Set(),
            segmentCount: 0,
            totalDailyVolume: 0,
            crossCount: 0,
            highRiskCount: 0,
            maxVCRatio: 0,
            minSpeed: null,
            travelTimeSum: 0,
          });
        }
        const entry = map.get(other);
        if (s.roadName) entry.roadNames.add(s.roadName);
        if (s.segmentId) entry.segmentIds.add(s.segmentId);
        entry.segmentCount += 1;
        entry.totalDailyVolume += Number(s.dailyVolume) || 0;
        entry.crossCount += s.isCrossCommunity ? 1 : 0;
        entry.highRiskCount += s.riskLevel === "高" ? 1 : 0;
        const vc = Number(s.vCRatio) || 0;
        entry.maxVCRatio = Math.max(entry.maxVCRatio, vc);
        const sp = Number(s.avgSpeedKmh);
        if (Number.isFinite(sp)) entry.minSpeed = entry.minSpeed === null ? sp : Math.min(entry.minSpeed, sp);
        entry.travelTimeSum += Number(s.travelTimeMin) || 0;
      });
      return Array.from(map.values())
        .map((x) => ({
          intersection_id: x.intersection_id,
          intersection_name: x.intersection_name,
          community_id: x.community_id,
          segmentIds: Array.from(x.segmentIds).join(" / "),
          roadNames: Array.from(x.roadNames).join(" / "),
          segmentCount: x.segmentCount,
          totalDailyVolume: Math.round(x.totalDailyVolume),
          crossCount: x.crossCount,
          highRiskCount: x.highRiskCount,
          maxVCRatio: Number(x.maxVCRatio.toFixed(3)),
          minSpeed: x.minSpeed === null ? "" : Number(x.minSpeed.toFixed(1)),
          avgTravelTimeMin: x.segmentCount ? Number((x.travelTimeSum / x.segmentCount).toFixed(2)) : 0,
        }))
        .sort((a, b) => Number(b.maxVCRatio) - Number(a.maxVCRatio));
    },
  },
  watch: {
    viewMode() {
      this.renderMap();
    },
    async activePage() {
      if (this.activePage !== "community") {
        this.selectedCommunityId = null;
        this.selectedCommunityRow = null;
      }

      if (this.activePage === "overview") {
        this.renderCharts();
        this.handleResize();
        return;
      }

      if (this.activePage === "map") {
        this.viewMode = "saturation";
      } else if (this.activePage === "community") {
        this.viewMode = "community";
        await Vue.nextTick();
        this.renderCommunityDelayChart();
        this.renderCommunityConnectivityChart();
        this.renderCommunitySelectedRadar();
      } else if (this.activePage === "key") {
        this.viewMode = "critical";
        await Vue.nextTick();
        this.renderKeyMetricsChart();
        this.renderKeyGroupChart();
        if (this.selectedRowForRadar) {
          this.renderNodeRadar(this.selectedRowForRadar);
        }
      } else if (this.activePage === "detail") {
        this.viewMode = "critical";
        if (!this.selectedNode && this.dashboard.nodes.length) {
          await this.openIntersection(this.dashboard.nodes[0]);
        } else if (this.selectedNode) {
          await this.openIntersection(this.selectedNode);
        }
      }

      await this.ensureMap();
      await Vue.nextTick();
      this.renderMap();
      this.handleResize();
    },
    detailVisible(value) {
      if (!value && this.detailChart) {
        this.detailChart.dispose();
        this.detailChart = null;
      }
    },
    selectedCommunityId() {
      this.renderMap();
    },
    showCrossEdges() {
      this.renderMap();
    },
    "filters.hour"() {
      if (!this.isAnalyzed) return;
      this.loadDashboard();
    },
  },
  async mounted() {
    console.log("App mounting...");
    try {
      // 检查依赖
      if (!window.Vue || !window.ElementPlus || !window.L || !window.echarts) {
        throw new Error("前端库加载失败，请检查网络或CDN连接");
      }

      await this.loadMeta();
      await this.loadStudyAreaNetwork();
      // 系统启动时仅加载基础元数据，不自动运行分析
      // await this.loadDashboard();
      window.addEventListener("resize", this.handleResize);
      
      // 成功加载后隐藏加载界面
      const loading = document.getElementById('app-loading');
      if (loading) loading.style.display = 'none';
      console.log("App mounted successfully");
    } catch (e) {
      console.error("Mount failed", e);
      const debug = document.getElementById('debug-info');
      if (debug) {
        debug.style.display = 'block';
        debug.innerHTML += `<div>启动失败: ${e.message}</div>`;
      }
      document.getElementById('retry-btn').style.display = 'block';
    }
  },
  beforeUnmount() {
    window.removeEventListener("resize", this.handleResize);
    Object.values(this.charts).forEach((chart) => chart && chart.dispose());
    if (this.detailChart) {
      this.detailChart.dispose();
    }
    if (this.map) {
      this.map.remove();
    }
  },
  methods: {
    handleFileChange(event, type) {
      this.importFiles[type] = event.target.files[0];
    },
    async submitImport() {
      if (!Object.values(this.importFiles).some((f) => f)) {
        ElementPlus.ElMessage.warning("请至少选择一个 CSV 文件进行上传");
        return;
      }
      this.importing = true;
      const formData = new FormData();
      if (this.importFiles.intersections) formData.append("intersections", this.importFiles.intersections);
      if (this.importFiles.road_segments) formData.append("road_segments", this.importFiles.road_segments);
      if (this.importFiles.hourly_traffic) formData.append("hourly_traffic", this.importFiles.hourly_traffic);
      if (this.importFiles.segment_daily) formData.append("segment_daily", this.importFiles.segment_daily);

      try {
        const res = await fetch("/api/import", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (data.success) {
          ElementPlus.ElMessage.success(data.message);
          this.showImportDialog = false;
          this.isAnalyzed = false; // 导入后重置分析状态
          await this.loadMeta();
        } else {
          ElementPlus.ElMessage.error(data.message);
        }
      } catch (err) {
        ElementPlus.ElMessage.error("上传失败: " + err.message);
      } finally {
        this.importing = false;
      }
    },
    async startAnalysis() {
      this.analyzing = true;
      try {
        const res = await fetch("/api/analyze", { method: "POST" });
        const data = await res.json();
        if (data.success) {
          ElementPlus.ElMessage.success("交通网络社区检测及关键路口分析完成！");
          this.isAnalyzed = true;
          await this.loadDashboard();
        } else {
          ElementPlus.ElMessage.error("分析失败");
        }
      } catch (err) {
        ElementPlus.ElMessage.error("分析过程中发生错误: " + err.message);
      } finally {
        this.analyzing = false;
      }
    },
    async loadMeta() {
      const response = await fetch("/api/meta");
      if (!response.ok) {
        throw new Error("meta request failed");
      }
      const data = await response.json();
      this.meta = data;
      this.filters.date = data.defaultDate;
      this.filters.hour = data.defaultHour;
    },
    async loadStudyAreaNetwork() {
      try {
        const response = await fetch("/static/study_area_network.json");
        if (response.ok) {
          this.studyAreaNetwork = await response.json();
          if (this.mapReady) {
            this.renderMap();
          }
        }
      } catch (e) {
        console.warn("Study area network data not found, skipping background highlight.");
      }
    },
    async loadDashboard() {
      this.loading = true;
      try {
        const params = new URLSearchParams({
          date: this.filters.date,
          hour: String(this.filters.hour),
        });
        const response = await fetch(`/api/dashboard?${params.toString()}`);
        if (!response.ok) {
          throw new Error("dashboard request failed");
        }
        const data = await response.json();
        // 补全排名
        if (data.charts && data.charts.topNodes) {
          data.charts.topNodes = data.charts.topNodes.map((node, index) => ({
            ...node,
            rank: index + 1
          }));
        }
        
        // 确保 communityInsights 是一个数组，即使后端返回为空
        if (!data.communityInsights) {
          data.communityInsights = [];
        }

        this.dashboard = data;
        this.mapFitted = false;
        if (this.activePage !== "overview") {
          await this.ensureMap();
          await Vue.nextTick();
          this.renderMap();
        }
        await Vue.nextTick();
        if (this.activePage === "overview") {
          this.renderCharts();
        }
        if (this.activePage === "community") {
          this.renderCommunityDelayChart();
          this.renderCommunityConnectivityChart();
          this.renderCommunitySelectedRadar();
        }
      } catch (error) {
        ElementPlus.ElMessage.error("分析数据加载失败");
      } finally {
        this.loading = false;
      }
    },
    async ensureMap() {
      if (this.mapReady && this.map) return;
      // 增加延迟至 850ms，确保 panel 的 rise 动画 (0.8s) 完全结束后再初始化地图
      await new Promise(resolve => setTimeout(resolve, 850));
      await Vue.nextTick();
      
      // 如果已经初始化过但 DOM 节点变化了，先移除
      if (this.map) {
        if (this.map._animatingZoom) {
          await new Promise((resolve) => this.map.once("zoomend", resolve));
        }
        try {
          if (this.edgeLayer) this.edgeLayer.clearLayers();
          if (this.nodeLayer) this.nodeLayer.clearLayers();
          if (this.boundaryLayer) this.boundaryLayer.clearLayers();
          this.edgeLayer = null;
          this.nodeLayer = null;
          this.boundaryLayer = null;
          this.map.remove();
          this.map = null;
          this.mapReady = false;
        } catch(e) {}
      }

      this.initMap();
      await Vue.nextTick();
      this.mapFitted = false;
      if (this.map) {
        this.map.invalidateSize();
      }
      this.handleResize();
    },
    initMap() {
      if (this.map) return;

      // GCJ-02 转 WGS-84 (将高德坐标转为 Leaflet 标准坐标)
      function gcj02ToWgs84(lng, lat) {
        var PI = Math.PI;
        var axis = 6378245.0;
        var offset = 0.00669342162296594323;
        
        function transformLat(x, y) {
          var ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
          ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
          ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
          ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
          return ret;
        }
        
        function transformLng(x, y) {
          var ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
          ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
          ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0;
          ret += (150.0 * Math.sin(x / 12.0 * PI) + 300.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
          return ret;
        }

        var dLat = transformLat(lng - 105.0, lat - 35.0);
        var dLng = transformLng(lng - 105.0, lat - 35.0);
        var radLat = lat / 180.0 * PI;
        var magic = Math.sin(radLat);
        magic = 1 - offset * magic * magic;
        var sqrtMagic = Math.sqrt(magic);
        dLat = (dLat * 180.0) / ((axis * (1 - offset)) / (magic * sqrtMagic) * PI);
        dLng = (dLng * 180.0) / (axis / sqrtMagic * Math.cos(radLat) * PI);
        return { lng: lng - dLng, lat: lat - dLat };
      }

      // WGS-84 转 GCJ-02 (用于高德地图瓦片对齐)
      function wgs84ToGcj02(lng, lat) {
        var PI = Math.PI;
        var axis = 6378245.0;
        var offset = 0.00669342162296594323;

        function transformLat(x, y) {
          var ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
          ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
          ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
          ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
          return ret;
        }

        function transformLng(x, y) {
          var ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
          ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
          ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0;
          ret += (150.0 * Math.sin(x / 12.0 * PI) + 300 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
          return ret;
        }

        var dLat = transformLat(lng - 105.0, lat - 35.0);
        var dLng = transformLng(lng - 105.0, lat - 35.0);
        var radLat = lat / 180.0 * PI;
        var magic = Math.sin(radLat);
        magic = 1 - offset * magic * magic;
        var sqrtMagic = Math.sqrt(magic);
        dLat = (dLat * 180.0) / ((axis * (1 - offset)) / (magic * sqrtMagic) * PI);
        dLng = (dLng * 180.0) / (axis / sqrtMagic * Math.cos(radLat) * PI);
        return { lng: lng + dLng, lat: lat + dLat };
      }

      // 暴露转换函数供渲染使用
      this.gcj02ToWgs84 = gcj02ToWgs84;

      // 自定义高德地图瓦片层：将 Leaflet 的 WGS-84 坐标转为 GCJ-02 请求瓦片
      L.TileLayer.GaoDe = L.TileLayer.extend({
        initialize: function(url, options) {
          L.TileLayer.prototype.initialize.call(this, url, options);
        },
        _getTiledPixelBounds: function(center) {
          var gcj = wgs84ToGcj02(center.lng, center.lat);
          var gcjCenter = L.latLng(gcj.lat, gcj.lng);
          return L.TileLayer.prototype._getTiledPixelBounds.call(this, gcjCenter);
        },
        _setZoomTransform: function(level, center, zoom) {
          var gcj = wgs84ToGcj02(center.lng, center.lat);
          var gcjCenter = L.latLng(gcj.lat, gcj.lng);
          return L.TileLayer.prototype._setZoomTransform.call(this, level, gcjCenter, zoom);
        }
      });
      
      L.tileLayer.gaoDe = function(url, options) {
        return new L.TileLayer.GaoDe(url, options);
      };

      this.map = L.map("map", {
        zoomControl: true,
        scrollWheelZoom: true,
        doubleClickZoom: true,
        touchZoom: true,
        attributionControl: true,
        maxZoom: 19,
      }).setView([34.8528, 105.6756], 16);

      this.mapTiles.amap = L.tileLayer.gaoDe(
        "https://wprd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        { attribution: '&copy; <a href="https://www.amap.com/">高德地图</a>', subdomains: "1234", maxZoom: 18 }
      );

      this.mapTiles.satellite = L.tileLayer.gaoDe(
        "https://wprd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=6&x={x}&y={y}&z={z}",
        { attribution: '&copy; <a href="https://www.amap.com/">高德地图</a>', subdomains: "1234" }
      );

      this.mapTiles.amap.addTo(this.map);

      const baseMaps = {
        "高德地图": this.mapTiles.amap,
        "卫星影像": this.mapTiles.satellite,
      };
      L.control.layers(baseMaps, null, { position: "topright" }).addTo(this.map);

      this.edgeLayer = L.layerGroup().addTo(this.map);
      this.nodeLayer = L.layerGroup().addTo(this.map);
      this.boundaryLayer = L.layerGroup().addTo(this.map); // 用于描绘研究区域边界
      this.mapReady = true;
      this.map.on("zoomend", () => {
        if (this.renderQueuedAfterZoom) {
          this.renderQueuedAfterZoom = false;
          this.renderMap();
          return;
        }
        if (this.showNodeAnnotations && this.viewMode !== "critical") {
          this.renderMap();
        }
      });
    },
    quantile(sorted, q) {
      if (!sorted.length) return 0;
      const idx = Math.floor((sorted.length - 1) * q);
      return sorted[Math.min(Math.max(idx, 0), sorted.length - 1)];
    },
    computeConvexHull(points) {
      if (points.length < 3) return points;
      
      // Graham Scan or Monotone Chain implementation
      const sorted = points.slice().sort((a, b) => a.lng !== b.lng ? a.lng - b.lng : a.lat - b.lat);
      
      const crossProduct = (o, a, b) => (a.lng - o.lng) * (b.lat - o.lat) - (a.lat - o.lat) * (b.lng - o.lng);
      
      const lower = [];
      for (let p of sorted) {
        while (lower.length >= 2 && crossProduct(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
          lower.pop();
        }
        lower.push(p);
      }
      
      const upper = [];
      for (let i = sorted.length - 1; i >= 0; i--) {
        const p = sorted[i];
        while (upper.length >= 2 && crossProduct(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
          upper.pop();
        }
        upper.push(p);
      }
      
      upper.pop();
      lower.pop();
      return lower.concat(upper).map(p => [p.lat, p.lng]);
    },
    computeFitBounds(nodes) {
      const points = [];
      const lats = [];
      const lngs = [];

      (nodes || []).forEach((node) => {
        const lat = Number(node.lat);
        const lng = Number(node.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
        points.push({ lat, lng });
        lats.push(lat);
        lngs.push(lng);
      });

      if (!points.length) return { points: [], outlierCount: 0 };

      lats.sort((a, b) => a - b);
      lngs.sort((a, b) => a - b);

      const latQ1 = this.quantile(lats, 0.25);
      const latQ3 = this.quantile(lats, 0.75);
      const lngQ1 = this.quantile(lngs, 0.25);
      const lngQ3 = this.quantile(lngs, 0.75);
      const latIqr = latQ3 - latQ1;
      const lngIqr = lngQ3 - lngQ1;

      const latLow = latQ1 - 1.5 * latIqr;
      const latHigh = latQ3 + 1.5 * latIqr;
      const lngLow = lngQ1 - 1.5 * lngIqr;
      const lngHigh = lngQ3 + 1.5 * lngIqr;

      const filtered = points.filter(
        (p) => p.lat >= latLow && p.lat <= latHigh && p.lng >= lngLow && p.lng <= lngHigh
      );

      const minKeep = Math.max(5, Math.floor(points.length * 0.6));
      if (filtered.length < minKeep) {
        return { points: points.map((p) => [p.lat, p.lng]), outlierCount: 0 };
      }

      return {
        points: filtered.map((p) => [p.lat, p.lng]),
        outlierCount: Math.max(points.length - filtered.length, 0),
      };
    },
    fitAllNodes() {
      if (!this.mapReady || !this.map) return;
      const bounds = (this.dashboard.nodes || [])
        .map((node) => [Number(node.lat), Number(node.lng)])
        .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
      if (!bounds.length) return;
      this.map.fitBounds(bounds, { padding: [32, 32] });
      this.mapFitted = true;
    },
    escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    },
    formatFixed(value, digits) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "-";
      return num.toFixed(digits);
    },
    buildNodeAnnotationHtml(node) {
      const name = this.escapeHtml(node.intersection_name || node.intersection_id || "");
      const communityId = Number(node.community_id);
      const communityText = Number.isFinite(communityId) ? `社区 ${communityId + 1}` : "社区 -";
      const scoreText = this.formatFixed(node.critical_score, 2);
      const satText = this.formatFixed(node.slot_saturation, 3);
      return `<div class="node-anno"><div class="node-anno-title">${name}</div><div class="node-anno-line">${communityText}</div><div class="node-anno-line">关键评分 ${scoreText}</div><div class="node-anno-line">饱和度 ${satText}</div></div>`;
    },
    buildNodeCompactLabel(node) {
      const communityId = Number(node.community_id);
      const score = Number(node.critical_score);
      const sat = Number(node.slot_saturation);
      if (this.viewMode === "saturation") {
        return this.formatFixed(sat, 2);
      }
      if (this.viewMode === "community") {
        return Number.isFinite(communityId) ? `社区${communityId + 1}` : "社区-";
      }
      if (this.viewMode === "critical") {
        if (!Number.isFinite(score)) return "";
        if (score >= 80) return "关键";
        if (score >= 60) return "关注";
        return "";
      }
      return Number.isFinite(communityId) ? `社区${communityId + 1}` : "";
    },
    renderMap() {
      if (!this.mapReady || !this.map || !document.getElementById('map') || !this.dashboard || !this.dashboard.nodes) {
        return;
      }

      if (this.map && this.map._animatingZoom) {
        this.renderQueuedAfterZoom = true;
        return;
      }

      // 检查地图实例是否有效
      try {
        this.edgeLayer.clearLayers();
        this.nodeLayer.clearLayers();
        this.boundaryLayer.clearLayers();
      } catch (e) {
        console.warn("Layer cleanup failed, re-initializing map...");
        this.mapReady = false;
        this.ensureMap();
        return;
      }

      const communityMembers =
        this.selectedCommunityId === null
          ? null
          : new Set(
              (this.dashboard.communities.find((c) => c.communityId === this.selectedCommunityId)?.members || [])
            );

      const validPoints = this.dashboard.nodes
        .map((n) => ({ lat: Number(n.lat), lng: Number(n.lng) }))
        .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));

      // --- 渲染路网背景 (按照用户代码样式) ---
      if (this.studyAreaNetwork) {
        L.geoJSON(this.studyAreaNetwork, {
          style: {
            color: "#3388ff", // 用户代码指定的蓝色
            weight: 4,        // 用户代码指定的线宽
            opacity: 0.8,     // 用户代码指定的透明度
            interactive: false,
            lineCap: "round",
            lineJoin: "round"
          }
        }).addTo(this.boundaryLayer);
      }

      // --- 可选：渲染四十个节点所在的区域凸包 ---
      if (validPoints.length >= 3) {
        const hullPoints = this.computeConvexHull(validPoints);
        L.polygon(hullPoints, {
          color: "#3388ff",
          weight: 1,
          opacity: 0.3,
          fillColor: "#3388ff",
          fillOpacity: 0.05,
          interactive: false
        }).addTo(this.boundaryLayer);
      }

      const communityAllowedIds =
        this.activePage === "community" && this.communityMapOnlyFiltered ? this.communityAllowedIdSet : null;

      this.dashboard.edges.forEach((edge) => {
        let opacity = 0.65;
        let isDimmed = false;

        if (this.activePage === "community" && communityMembers) {
          const inFrom = communityMembers.has(edge.from_intersection);
          const inTo = communityMembers.has(edge.to_intersection);
          const isInternal = inFrom && inTo;
          const isCross = (inFrom && !inTo) || (!inFrom && inTo);
          
          if (!isInternal && !isCross) {
            if (this.communityMapOnlyFiltered) return;
            opacity = 0.1;
            isDimmed = true;
          }
        }

        const polyline = L.polyline((this.gcj02ToWgs84 && (edge.path || []).length > 0) ? (edge.path || []).map(p => { const wgs = this.gcj02ToWgs84(p[0], p[1]); return [wgs.lng, wgs.lat]; }) : edge.path, {
          color: this.edgeColor(edge),
          weight: isDimmed ? 1 : this.edgeWeight(edge),
          opacity: opacity,
          lineCap: "round",
          lineJoin: "round",
          smoothFactor: 1.2,
          className: !isDimmed && this.showFlowAnimation && edge.v_c_ratio >= 0.75 ? "flow-animation-high" : (!isDimmed && this.showFlowAnimation && edge.v_c_ratio >= 0.55 ? "flow-animation-mid" : ""),
          dashArray:
            this.activePage === "community" && (edge.is_cross_community || isDimmed) ? "6 8" : null,
        });
        polyline.bindTooltip(
          `${edge.road_name}<br>V/C: ${edge.v_c_ratio}<br>平均速度: ${edge.avg_speed_kmh} km/h`,
          { sticky: true }
        );
        this.edgeLayer.addLayer(polyline);
      });

      const bounds = [];
      const renderedNodeIds = new Set();
      
      (this.dashboard.nodes || []).forEach((node) => {
        if (!node.intersection_id || renderedNodeIds.has(node.intersection_id)) return;
        renderedNodeIds.add(node.intersection_id);

        let lat = Number(node.lat);
        let lng = Number(node.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        // 将 GCJ-02 坐标转换为 WGS-84 供 Leaflet 使用
        if (this.gcj02ToWgs84) {
          const wgs = this.gcj02ToWgs84(lng, lat);
          lng = wgs.lng;
          lat = wgs.lat;
        }

        let opacity = 0.55;
        let fillOpacity = 0.68;
        let isDimmed = false;

        if (this.activePage === "community" && communityMembers) {
          if (!communityMembers.has(node.intersection_id)) {
            if (this.communityMapOnlyFiltered) return;
            opacity = 0.15;
            fillOpacity = 0.15;
            isDimmed = true;
          }
        }

        const isSelected = this.selectedNode && this.selectedNode.intersection_id === node.intersection_id;
        const marker = L.circleMarker([lat, lng], {
           radius: this.nodeRadius(node) + (isSelected ? 3 : 0),
           fillColor: isDimmed ? "#94a3b8" : (isSelected ? "#fff" : this.nodeColor(node)), // 选中时白色填充
           color: isSelected ? "red" : (isDimmed ? "#94a3b8" : this.nodeColor(node)), // 选中时红色边框
          weight: isSelected ? 3 : (isDimmed ? 0.2 : 1.5), // 边框加粗
          opacity: isSelected ? 1 : opacity,
          fillOpacity: isSelected ? 1 : fillOpacity,
        });

        if (this.showNodeAnnotations) {
          if (this.viewMode === "critical") {
            const score = Number(node.critical_score) || 0;
            if (score >= 80) {
              marker.bindTooltip("关键", {
                permanent: true,
                direction: "center",
                className: "node-label node-label-high",
                opacity: 0.95,
              });
            } else if (score >= 60) {
              marker.bindTooltip("关注", {
                permanent: true,
                direction: "center",
                className: "node-label node-label-mid",
                opacity: 0.9,
              });
            }
          } else {
            const compact = (this.map && this.map.getZoom && this.map.getZoom() < 15);
            if (compact) {
              const label = this.buildNodeCompactLabel(node);
              if (label) {
                marker.bindTooltip(label, {
                  permanent: true,
                  direction: "center",
                  className: "node-label node-label-compact",
                  opacity: 0.92,
                });
              }
            } else {
              marker.bindTooltip(this.buildNodeAnnotationHtml(node), {
                permanent: true,
                direction: "auto",
                offset: [0, -10],
                className: "node-anno-tooltip",
                opacity: 0.96,
              });
            }
          }
        } else {
          marker.bindTooltip(
            `<div class="tooltip-card"><strong>${this.escapeHtml(node.intersection_name)}</strong><br>社区 ${
              Number(node.community_id) + 1
            }<br>关键评分 ${this.escapeHtml(node.critical_score)}<br>饱和度 ${this.escapeHtml(node.slot_saturation)}</div>`,
            { sticky: true }
          );
        }
        marker.on("click", () => this.openIntersection(node));
        this.nodeLayer.addLayer(marker);
        bounds.push([Number(node.lat), Number(node.lng)]);
      });

      if (!this.mapFitted && bounds.length) {
        this.outlierCount = 0;
        this.map.fitBounds(bounds, { padding: [48, 48] });
        this.mapFitted = true;
      }
    },
    renderCharts() {
      if (!this.dashboard || !this.dashboard.charts) return;
      Vue.nextTick(() => {
        this.renderCommunityChart();
        this.renderTrendChart();
        this.renderZoneChart();
        if (this.activePage === "key") {
          this.renderKeyMetricsChart();
          this.renderKeyGroupChart();
          if (this.selectedRowForRadar) {
            this.renderNodeRadar(this.selectedRowForRadar);
          }
        }
      });
    },
    renderCommunityChart() {
      const dom = document.getElementById("community-chart");
      if (!dom) return;
      this.charts.community = this.charts.community || echarts.init(dom);

      const rows = this.dashboard.charts.communityStats || [];
      const option = {
        animationDuration: 800,
        tooltip: { trigger: "axis" },
        grid: { left: 40, right: 20, top: 40, bottom: 45, containLabel: true },
        xAxis: {
          type: "category",
          axisLabel: { color: "#42526a" },
          data: rows.map((item) => `社区${item.communityId + 1}`),
        },
        yAxis: [
          {
            type: "value",
            name: "规模",
            axisLabel: { color: "#42526a" },
          },
          {
            type: "value",
            name: "平均饱和度",
            axisLabel: { color: "#42526a" },
          },
        ],
        series: [
          {
            type: "bar",
            barWidth: 28,
            itemStyle: {
              borderRadius: [10, 10, 0, 0],
              color: (params) => communityPalette[params.dataIndex % communityPalette.length],
            },
            data: rows.map((item) => item.size),
          },
          {
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            lineStyle: { width: 3, color: "#f97316" },
            symbolSize: 8,
            data: rows.map((item) => item.avgSaturation),
          },
        ],
      };
      this.charts.community.setOption(option);
    },
    renderTrendChart() {
      const dom = document.getElementById("trend-chart");
      if (!dom) return;
      this.charts.trend = this.charts.trend || echarts.init(dom);
      const rows = this.dashboard.charts.hourlyTrend || [];
      const option = {
        animationDuration: 900,
        tooltip: { trigger: "axis" },
        legend: { data: ["总车流", "平均速度", "平均饱和度"] },
        grid: { left: 45, right: 40, top: 45, bottom: 45, containLabel: true },
        xAxis: {
          type: "category",
          data: rows.map((item) => `${item.hour}:00`),
        },
        yAxis: [
          { type: "value", name: "车流量" },
          { type: "value", name: "速度/饱和度" },
        ],
        series: [
          {
            name: "总车流",
            type: "bar",
            barMaxWidth: 18,
            itemStyle: {
              color: "rgba(15, 118, 110, 0.88)",
              borderRadius: [8, 8, 0, 0],
            },
            data: rows.map((item) => item.totalVeh),
          },
          {
            name: "平均速度",
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            symbol: "circle",
            symbolSize: 8,
            lineStyle: { width: 3, color: "#2563eb" },
            data: rows.map((item) => item.avgSpeedKmh),
          },
          {
            name: "平均饱和度",
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            symbol: "circle",
            symbolSize: 8,
            lineStyle: { width: 3, color: "#f97316" },
            data: rows.map((item) => item.avgSaturation),
          },
        ],
      };
      this.charts.trend.setOption(option);
    },
    renderZoneChart() {
      const dom = document.getElementById("zone-chart");
      if (!dom) return;
      this.charts.zone = this.charts.zone || echarts.init(dom);
      const rows = this.dashboard.charts.zoneLoad || [];
      const option = {
        animationDuration: 850,
        tooltip: { trigger: "axis" },
        grid: { left: 45, right: 30, top: 40, bottom: 60, containLabel: true },
        xAxis: {
          type: "category",
          axisLabel: { interval: 0, rotate: 20 },
          data: rows.map((item) => item.functional_zone),
        },
        yAxis: [
          { type: "value", name: "总车流" },
          { type: "value", name: "平均饱和度" },
        ],
        series: [
          {
            type: "bar",
            yAxisIndex: 0,
            barWidth: 20,
            itemStyle: {
              color: "#1d4ed8",
              borderRadius: [8, 8, 0, 0],
            },
            data: rows.map((item) => item.totalVeh),
          },
          {
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            lineStyle: { width: 3, color: "#ef4444" },
            areaStyle: { color: "rgba(239, 68, 68, 0.12)" },
            data: rows.map((item) => item.avgSaturation),
          },
        ],
      };
      this.charts.zone.setOption(option);
    },
    renderKeyMetricsChart() {
      const dom = document.getElementById("key-metric-chart");
      if (!dom) return;
      this.charts.keyMetric = this.charts.keyMetric || echarts.init(dom);
      const rows = this.topNodesDisplayed || [];
      this.charts.keyMetric.setOption({
        animationDuration: 900,
        tooltip: { trigger: "axis" },
        legend: { data: ["流量", "延误", "排队长度"] },
        grid: { left: 42, right: 22, top: 32, bottom: 36 },
        xAxis: {
          type: "category",
          axisLabel: { interval: 0, rotate: 25 },
          data: rows.map((item) => item.intersection_id),
        },
        yAxis: [{ type: "value", name: "流量/长度" }, { type: "value", name: "延误(s)" }],
        series: [
          {
            name: "流量",
            type: "bar",
            barWidth: 14,
            itemStyle: { color: "#2563eb", borderRadius: [6, 6, 0, 0] },
            data: rows.map((item) => item.slot_total_veh),
          },
          {
            name: "延误",
            type: "line",
            yAxisIndex: 1,
            smooth: true,
            lineStyle: { color: "#ef4444", width: 3 },
            data: rows.map((item) => item.slot_delay_s),
          },
          {
            name: "排队长度",
            type: "line",
            smooth: true,
            lineStyle: { color: "#f59e0b", width: 3 },
            data: rows.map((item) => item.slot_queue_m),
          },
        ],
      });
      // 雷达图（评分构成）
      const rdom = document.getElementById("key-radar-chart");
      if (rdom) {
        this.charts.keyRadar = this.charts.keyRadar || echarts.init(rdom);
        const avg = (key) => {
          if (!rows.length) return 0;
          const vals = rows.map((r) => Number(r[key]) || 0);
          return vals.reduce((a, b) => a + b, 0) / rows.length;
        };
        const data = [
          avg("betweenness_norm"),
          avg("degree_norm"),
          avg("flow_norm"),
          avg("delay_norm"),
          avg("queue_norm"),
        ];
        this.charts.keyRadar.setOption({
          animationDuration: 800,
          tooltip: {},
          radar: {
            indicator: [
              { name: "介数中心", max: 1 },
              { name: "节点度", max: 1 },
              { name: "流量", max: 1 },
              { name: "延误", max: 1 },
              { name: "排队", max: 1 },
            ],
            splitNumber: 4,
          },
          series: [
            {
              type: "radar",
              areaStyle: { opacity: 0.2 },
              lineStyle: { width: 2 },
              data: [{ value: data, name: "平均构成" }],
            },
          ],
        });
      }
    },
    onRankControlChange() {
      if (this.activePage === "key") {
        this.renderKeyMetricsChart();
        this.renderKeyGroupChart();
        if (this.selectedRowForRadar) {
          this.renderNodeRadar(this.selectedRowForRadar);
        }
      }
    },
    onCommunityControlChange() {
      if (this.activePage === "community") {
        this.renderMap();
        this.renderCommunityDelayChart();
        this.renderCommunityConnectivityChart();
        this.renderCommunitySelectedRadar();
      }
    },
    communityCrossRatio(row) {
      const cross = Number(row && row.crossEdgeCount) || 0;
      const internal = Number(row && row.internalEdgeCount) || 0;
      const base = cross + internal;
      if (!base) return 0;
      return Number(((cross / base) * 100).toFixed(1));
    },
    exportCommunityCSV() {
      const rows = this.communityInsightsDisplayed || [];
      const headers = [
        "communityId",
        "size",
        "totalVeh",
        "avgDelayS",
        "avgSpeedKmh",
        "avgSaturation",
        "internalEdgeCount",
        "crossEdgeCount",
        "congestionLevel",
        "dominantZone",
      ];
      const csv = [
        headers.join(","),
        ...rows.map((r) =>
          headers.map((h) => (r[h] !== undefined ? String(r[h]).replace(/,/g, " ") : "")).join(",")
        ),
      ].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `社区指标评估_${this.filters.date}_${this.filters.hour}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
    exportCommunityXLSX() {
      if (typeof XLSX === "undefined") {
        ElementPlus.ElMessage.warning("未能加载 Excel 库，已为你保留 CSV 导出");
        this.exportCommunityCSV();
        return;
      }
      const rows = this.communityInsightsDisplayed || [];
      const sheet = XLSX.utils.json_to_sheet(rows);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, sheet, "Community");
      const filename = `社区指标评估_${this.filters.date}_${this.filters.hour}.xlsx`;
      XLSX.writeFile(wb, filename);
    },
    renderCommunityDelayChart() {
      const dom = document.getElementById("community-delay-chart");
      if (!dom) return;
      this.charts.communityDelay = this.charts.communityDelay || echarts.init(dom);
      const rows = this.communityInsightsDisplayed || [];
      this.charts.communityDelay.setOption({
        animationDuration: 800,
        tooltip: { trigger: "axis" },
        grid: { left: 42, right: 22, top: 32, bottom: 36 },
        xAxis: {
          type: "category",
          axisLabel: { interval: 0, rotate: 20 },
          data: rows.map((r) => `社区${Number(r.communityId) + 1}`),
        },
        yAxis: [{ type: "value", name: "平均延误(s)" }, { type: "value", name: "总流量" }],
        series: [
          {
            name: "平均延误",
            type: "bar",
            barWidth: 16,
            itemStyle: { color: "#ef4444", borderRadius: [6, 6, 0, 0] },
            data: rows.map((r) => Number(r.avgDelayS) || 0),
          },
          {
            name: "总流量",
            type: "line",
            yAxisIndex: 1,
            smooth: true,
            lineStyle: { color: "#2563eb", width: 3 },
            data: rows.map((r) => Number(r.totalVeh) || 0),
          },
        ],
      });
    },
    renderCommunityConnectivityChart() {
      const dom = document.getElementById("community-connectivity-chart");
      if (!dom) return;
      this.charts.communityConnectivity = this.charts.communityConnectivity || echarts.init(dom);
      const rows = this.communityInsightsDisplayed || [];
      this.charts.communityConnectivity.setOption({
        animationDuration: 800,
        tooltip: { trigger: "axis" },
        legend: { data: ["内部路段", "跨区连接", "跨区比例(%)"] },
        grid: { left: 42, right: 22, top: 32, bottom: 36 },
        xAxis: {
          type: "category",
          axisLabel: { interval: 0, rotate: 20 },
          data: rows.map((r) => `社区${Number(r.communityId) + 1}`),
        },
        yAxis: [{ type: "value", name: "连接数量" }, { type: "value", name: "跨区比例(%)", max: 100 }],
        series: [
          {
            name: "内部路段",
            type: "bar",
            stack: "conn",
            barWidth: 16,
            itemStyle: { color: "#2563eb", borderRadius: [6, 6, 0, 0] },
            data: rows.map((r) => Number(r.internalEdgeCount) || 0),
          },
          {
            name: "跨区连接",
            type: "bar",
            stack: "conn",
            itemStyle: { color: "#ef4444", borderRadius: [6, 6, 0, 0] },
            data: rows.map((r) => Number(r.crossEdgeCount) || 0),
          },
          {
            name: "跨区比例(%)",
            type: "line",
            yAxisIndex: 1,
            smooth: true,
            lineStyle: { color: "#f59e0b", width: 3 },
            data: rows.map((r) => this.communityCrossRatio(r)),
          },
        ],
      });
    },
    renderCommunitySelectedRadar() {
      const dom = document.getElementById("community-selected-radar");
      if (!dom) return;
      this.charts.communityRadar = this.charts.communityRadar || echarts.init(dom);
      const rows = this.communityInsightsDisplayed || [];
      const row = this.selectedCommunityRow || (rows.length ? rows[0] : null);
      if (!row) return;
      const maxDelay = Math.max(...rows.map((c) => Number(c.avgDelayS) || 0), 1);
      const maxFlow = Math.max(...rows.map((c) => Number(c.totalVeh) || 0), 1);
      const maxCross = Math.max(...rows.map((c) => Number(c.crossEdgeCount) || 0), 1);
      const maxInternal = Math.max(...rows.map((c) => Number(c.internalEdgeCount) || 0), 1);
      const maxSpeed = Math.max(...rows.map((c) => Number(c.avgSpeedKmh) || 0), 1);
      const clamp01 = (v) => Math.max(0, Math.min(1, Number(v) || 0));
      const value = [
        clamp01((Number(row.avgDelayS) || 0) / maxDelay),
        clamp01(1 - (Number(row.avgSpeedKmh) || 0) / maxSpeed),
        clamp01(Number(row.avgSaturation) || 0),
        clamp01((Number(row.totalVeh) || 0) / maxFlow),
        clamp01((Number(row.crossEdgeCount) || 0) / maxCross),
        clamp01((Number(row.internalEdgeCount) || 0) / maxInternal),
      ];
      this.charts.communityRadar.setOption({
        animationDuration: 800,
        tooltip: {},
        radar: {
          indicator: [
            { name: "延误(归一)", max: 1 },
            { name: "低速(归一)", max: 1 },
            { name: "饱和(0-1)", max: 1 },
            { name: "流量(归一)", max: 1 },
            { name: "跨区(归一)", max: 1 },
            { name: "内部路段(归一)", max: 1 },
          ],
          splitNumber: 4,
        },
        series: [{ type: "radar", areaStyle: { opacity: 0.2 }, data: [{ value, name: `社区${Number(row.communityId) + 1}` }] }],
      });
    },
    exportRankingXLSX() {
      if (typeof XLSX === "undefined") {
        ElementPlus.ElMessage.warning("未能加载 Excel 库，已为你保留 CSV 导出");
        this.exportRankingCSV();
        return;
      }
      const rows = this.topNodesDisplayed || [];
      const sheet = XLSX.utils.json_to_sheet(rows);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, sheet, "Ranking");
      const filename = `关键路口排行榜_${this.filters.date}_${this.filters.hour}.xlsx`;
      XLSX.writeFile(wb, filename);
    },
    renderKeyGroupChart() {
      const dom = document.getElementById("key-group-chart");
      if (!dom) return;
      this.charts.keyGroup = this.charts.keyGroup || echarts.init(dom);
      const comm = (this.dashboard.charts.communityStats || []).slice();
      const zones = (this.dashboard.charts.zoneLoad || []).slice();
      const order = this.groupSortOrder === "asc" ? 1 : -1;
      const commMetric = this.groupCommunitySortMetric;
      const zoneMetric = this.groupZoneSortMetric;
      comm.sort((a, b) => (Number(a[commMetric]) - Number(b[commMetric])) * order);
      zones.sort((a, b) => (Number(a[zoneMetric]) - Number(b[zoneMetric])) * order);
      this.charts.keyGroup.setOption({
        animationDuration: 800,
        tooltip: { trigger: "axis" },
        legend: { data: ["社区平均评分", "社区平均饱和度", "功能区总车流", "功能区关键路口数"] },
        grid: { left: 42, right: 22, top: 32, bottom: 36 },
        xAxis: [
          { type: "category", data: comm.map((c) => `社区${c.communityId + 1}`) },
          { type: "category", data: zones.map((z) => z.functional_zone) },
        ],
        yAxis: [{ type: "value" }, { type: "value" }],
        series: [
          {
            name: "社区平均评分",
            type: "bar",
            xAxisIndex: 0,
            yAxisIndex: 0,
            barWidth: 14,
            itemStyle: { color: "#2563eb", borderRadius: [6, 6, 0, 0] },
            data: comm.map((c) => c.avgCriticalScore),
          },
          {
            name: "社区平均饱和度",
            type: "line",
            xAxisIndex: 0,
            yAxisIndex: 1,
            smooth: true,
            lineStyle: { color: "#f59e0b", width: 3 },
            data: comm.map((c) => c.avgSaturation),
          },
          {
            name: "功能区总车流",
            type: "bar",
            xAxisIndex: 1,
            yAxisIndex: 0,
            barWidth: 14,
            itemStyle: { color: "#0f766e", borderRadius: [6, 6, 0, 0] },
            data: zones.map((z) => z.totalVeh),
          },
          {
            name: "功能区关键路口数",
            type: "line",
            xAxisIndex: 1,
            yAxisIndex: 1,
            smooth: true,
            lineStyle: { color: "#ef4444", width: 3 },
            data: zones.map((z) => z.keyNodeCount),
          },
        ],
      });
    },
    renderNodeRadar(row) {
      const dom = document.getElementById("key-node-radar");
      if (!dom || !row) return;
      this.selectedRowForRadar = row;
      this.charts.keyNodeRadar = this.charts.keyNodeRadar || echarts.init(dom);
      const value = [
        Number(row.betweenness_norm) || 0,
        Number(row.degree_norm) || 0,
        Number(row.flow_norm) || 0,
        Number(row.delay_norm) || 0,
        Number(row.queue_norm) || 0,
      ];
      this.charts.keyNodeRadar.setOption({
        animationDuration: 800,
        tooltip: {},
        radar: {
          indicator: [
            { name: "介数中心", max: 1 },
            { name: "节点度", max: 1 },
            { name: "流量", max: 1 },
            { name: "延误", max: 1 },
            { name: "排队", max: 1 },
          ],
        },
        series: [{ type: "radar", areaStyle: { opacity: 0.2 }, data: [{ value, name: row.intersection_id }] }],
      });
    },
    exportRankingCSV() {
      const rows = this.topNodesDisplayed || [];
      const headers = [
        "rank",
        "intersection_id",
        "intersection_name",
        "critical_score",
        "slot_total_veh",
        "slot_delay_s",
        "slot_queue_m",
        "slot_saturation",
        "community_id",
        "functional_zone",
        "betweenness_norm",
        "degree_norm",
        "flow_norm",
        "delay_norm",
        "queue_norm",
      ];
      const csv = [
        headers.join(","),
        ...rows.map((r) => headers.map((h) => (r[h] !== undefined ? String(r[h]).replace(/,/g, " ") : "")).join(",")),
      ].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `关键路口排行榜_${this.filters.date}_${this.filters.hour}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
    exportChartCommand(command) {
      if (command === "all") {
        this.exportEchartsChartImage("keyMetric", "关键路口_指标图");
        this.exportEchartsChartImage("keyRadar", "关键路口_TopN构成雷达");
        this.exportEchartsChartImage("keyNodeRadar", "关键路口_单点构成雷达");
        this.exportEchartsChartImage("keyGroup", "关键路口_分组统计图");
        return;
      }
      const mapping = {
        keyMetric: "关键路口_指标图",
        keyRadar: "关键路口_TopN构成雷达",
        keyNodeRadar: "关键路口_单点构成雷达",
        keyGroup: "关键路口_分组统计图",
      };
      this.exportEchartsChartImage(command, mapping[command] || "chart");
    },
    exportEchartsChartImage(chartKey, filenamePrefix) {
      const chart = this.charts[chartKey];
      if (!chart) {
        ElementPlus.ElMessage.warning("图表尚未渲染，请先打开关键路口页签");
        return;
      }
      const url = chart.getDataURL({
        type: "png",
        pixelRatio: 2,
        backgroundColor: "#ffffff",
      });
      const a = document.createElement("a");
      a.href = url;
      a.download = `${filenamePrefix}_${this.filters.date}_${this.filters.hour}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    },
    scoreBreakdown(row) {
      if (!row) return [];
      const items = [
        { key: "betweenness_norm", name: "介数中心性", weight: scoreWeights.betweenness },
        { key: "degree_norm", name: "节点度", weight: scoreWeights.degree },
        { key: "flow_norm", name: "流量", weight: scoreWeights.flow },
        { key: "delay_norm", name: "延误", weight: scoreWeights.delay },
        { key: "queue_norm", name: "排队", weight: scoreWeights.queue },
      ].map((item) => {
        const norm = Number(row[item.key]) || 0;
        const contrib = norm * item.weight;
        return { ...item, norm, contrib };
      });
      const sum = items.reduce((acc, item) => acc + item.contrib, 0) || 1;
      return items.map((item) => ({
        ...item,
        norm: Number(item.norm.toFixed(3)),
        contrib: Number(item.contrib.toFixed(3)),
        percent: Number(((item.contrib / sum) * 100).toFixed(1)),
      }));
    },
    async openIntersection(node) {
      this.selectedNode = node;
      this.detailIntersectionId = node.intersection_id;
      this.detailVisible = true;
      try {
        const params = new URLSearchParams({ date: this.filters.date });
        const response = await fetch(`/api/intersections/${node.intersection_id}?${params.toString()}`);
        if (!response.ok) {
          throw new Error("detail request failed");
        }
        this.intersectionDetail = await response.json();
        await Vue.nextTick();
        this.renderDetailChart();
        this.renderMap();
      } catch (error) {
        ElementPlus.ElMessage.error("路口详情加载失败");
      }
    },
    async onDetailIntersectionChange(value) {
      if (!value) return;
      const node = (this.dashboard.nodes || []).find((n) => n.intersection_id === value);
      if (node) {
        if (this.map) {
          this.map.setView([node.lat, node.lng], 15, { animate: true });
        }
        await this.openIntersection(node);
      }
    },
    async openNeighbor(row) {
      if (!row || !row.intersection_id) return;
      await this.onDetailIntersectionChange(row.intersection_id);
    },
    async openSegment(row) {
      if (!row || !row.otherEnd) return;
      await this.onDetailIntersectionChange(row.otherEnd);
    },
    async goDetailPrev() {
      const idx = this.detailIndex;
      if (idx <= 0) return;
      const row = this.detailOrderedRows[idx - 1];
      await this.onDetailIntersectionChange(row.intersection_id);
    },
    async goDetailNext() {
      const idx = this.detailIndex;
      if (idx < 0) return;
      const row = this.detailOrderedRows[idx + 1];
      if (!row) return;
      await this.onDetailIntersectionChange(row.intersection_id);
    },
    exportIntersectionCSV() {
      if (!this.selectedNode) return;
      const rows = (this.intersectionDetail && this.intersectionDetail.timeseries) ? this.intersectionDetail.timeseries : [];
      const headers = ["hour", "inboundVeh", "outboundVeh", "totalVeh", "avgSpeedKmh", "avgDelayS", "queueLengthM", "saturation"];
      const csv = [
        headers.join(","),
        ...rows.map((r) => headers.map((h) => (r[h] !== undefined ? String(r[h]).replace(/,/g, " ") : "")).join(",")),
      ].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `路口详情_${this.selectedNode.intersection_id}_${this.filters.date}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
    exportIntersectionXLSX() {
      if (!this.selectedNode) return;
      if (typeof XLSX === "undefined") {
        ElementPlus.ElMessage.warning("未能加载 Excel 库，已为你保留 CSV 导出");
        this.exportIntersectionCSV();
        return;
      }
      const rows = (this.intersectionDetail && this.intersectionDetail.timeseries) ? this.intersectionDetail.timeseries : [];
      const sheet = XLSX.utils.json_to_sheet(rows);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, sheet, "Timeseries");
      XLSX.writeFile(wb, `路口详情_${this.selectedNode.intersection_id}_${this.filters.date}.xlsx`);
    },
    exportIntersectionChartPNG() {
      if (!this.detailChart || !this.selectedNode) {
        ElementPlus.ElMessage.warning("趋势图尚未渲染");
        return;
      }
      const url = this.detailChart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#ffffff" });
      const a = document.createElement("a");
      a.href = url;
      a.download = `路口趋势图_${this.selectedNode.intersection_id}_${this.filters.date}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    },
    renderDetailChart() {
      const dom =
        (this.activePage === "detail" && document.getElementById("detail-page-chart")) ||
        document.getElementById("detail-chart");
      if (!dom || !this.intersectionDetail.timeseries.length) return;
      this.detailChart = this.detailChart || echarts.init(dom);
      const rows = this.intersectionDetail.timeseries;
      this.detailChart.setOption({
        animationDuration: 700,
        tooltip: { trigger: "axis" },
        legend: { data: ["车流量", "平均速度", "平均延误"] },
        grid: { left: 42, right: 30, top: 32, bottom: 28 },
        xAxis: {
          type: "category",
          data: rows.map((item) => `${item.hour}:00`),
        },
        yAxis: [
          { type: "value", name: "车流量" },
          { type: "value", name: "速度/延误" },
        ],
        series: [
          {
            name: "车流量",
            type: "bar",
            barMaxWidth: 14,
            itemStyle: { color: "#0f766e", borderRadius: [6, 6, 0, 0] },
            data: rows.map((item) => item.totalVeh),
          },
          {
            name: "平均速度",
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            lineStyle: { width: 3, color: "#2563eb" },
            data: rows.map((item) => item.avgSpeedKmh),
          },
          {
            name: "平均延误",
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            lineStyle: { width: 3, color: "#f97316" },
            data: rows.map((item) => item.avgDelayS),
          },
        ],
      });
    },
    focusTopCritical() {
      const node = this.dashboard.nodes[0];
      if (!node || !this.map) return;
      this.map.setView([node.lat, node.lng], 15, { animate: true });
      this.openIntersection(node);
    },
    selectTopNode(row) {
      const node = this.dashboard.nodes.find(
        (item) => item.intersection_id === row.intersection_id
      );
      if (!node) return;
      this.map.setView([node.lat, node.lng], 15, { animate: true });
      this.openIntersection(node);
      this.renderNodeRadar(row);
    },
    focusCommunityRow(row) {
      this.selectedCommunityId = row.communityId;
      this.selectedCommunityRow = row;
      const node = this.dashboard.nodes.find((item) => item.community_id === row.communityId);
      if (!node || !this.map) return;
      this.map.setView([node.lat, node.lng], 14, { animate: true });
      this.renderMap();
      this.renderCommunitySelectedRadar();
    },
    nodeColor(node) {
      if (this.activePage === "community" || this.viewMode === "community") {
        return this.communityColor(node.community_id);
      }
      if (this.viewMode === "critical") {
        if (node.critical_score >= 80) return "#991b1b";
        if (node.critical_score >= 60) return "#ea580c";
        return "#16a34a";
      }
      // 优化拥堵压力颜色逻辑
      const sat = Number(node.slot_saturation) || 0;
      if (sat >= 0.75) return "#b91c1c"; // 高压：深红
      if (sat >= 0.55) return "#f59e0b"; // 中压：橙黄
      if (sat >= 0.35) return "#10b981"; // 低压：翠绿
      return "#94a3b8"; // 极低压力/空闲：灰蓝
    },
    edgeColor(edge) {
      if (this.viewMode === "community") {
        if (edge.is_cross_community) return "#94a3b8";
        return this.communityColor(edge.from_community);
      }

      if (this.viewMode === "saturation") {
        const v = Number(edge.v_c_ratio) || 0;
        if (v >= 0.9) return "#b91c1c";
        if (v >= 0.75) return "#f59e0b";
        if (v >= 0.55) return "#10b981";
        return "rgba(148, 163, 184, 0.85)";
      }

      if (this.viewMode === "critical") {
        const score = Math.max(this._getNodeScore(edge.from_intersection), this._getNodeScore(edge.to_intersection));
        if (score >= 80) return "#991b1b";
        if (score >= 60) return "#ea580c";
        return "rgba(148, 163, 184, 0.7)";
      }

      if (edge.risk_level === "高") return "#991b1b";
      if (edge.risk_level === "中") return "#d97706";
      return "rgba(30, 64, 175, 0.6)";
    },
    edgeWeight(edge) {
      if (this.viewMode === "community") {
        return edge.is_cross_community ? 2.2 : 2.8;
      }

      if (this.viewMode === "saturation") {
        const v = Number(edge.v_c_ratio) || 0;
        if (v >= 0.9) return 4.4;
        if (v >= 0.75) return 3.4;
        if (v >= 0.55) return 2.6;
        if (v >= 0.35) return 2.0;
        return 1.4;
      }

      if (this.viewMode === "critical") {
        const score = Math.max(this._getNodeScore(edge.from_intersection), this._getNodeScore(edge.to_intersection));
        if (score >= 80) return 4.0;
        if (score >= 60) return 3.0;
        return 1.6;
      }

      if (edge.v_c_ratio >= 0.75) return 4;
      if (edge.v_c_ratio >= 0.55) return 3;
      return 1.5;
    },
    nodeRadius(node) {
      if (this.viewMode === "saturation") {
        const sat = Number(node.slot_saturation) || 0;
        return 5 + sat * 8; // 拥堵压力视图下，半径随饱和度增大而增大，更直观
      }
      if (this.viewMode === "critical") {
        const score = Number(node.critical_score) || 0;
        if (score >= 80) return 9;
        if (score >= 60) return 7;
        return 5.2;
      }
      return 4.2 + Math.min(node.critical_score / 18, 4.6);
    },
    communityColor(id) {
      const index = ((id % communityPalette.length) + communityPalette.length) % communityPalette.length;
      return communityPalette[index];
    },
    _getNodeScore(intersectionId) {
      const nodes = this.dashboard && this.dashboard.nodes ? this.dashboard.nodes : [];
      const node = nodes.find((x) => x.intersection_id === intersectionId);
      return node ? Number(node.critical_score) || 0 : 0;
    },
    riskTagType(level) {
      if (level === "高") return "danger";
      if (level === "中") return "warning";
      return "success";
    },
    handleResize() {
      const allCharts = [
        ...Object.values(this.charts),
        this.detailChart,
        this.charts.keyGroup,
        this.charts.keyRadar,
        this.charts.keyNodeRadar,
        this.charts.communityDelay,
        this.charts.communityConnectivity,
        this.charts.communityRadar,
      ];
      allCharts.forEach((chart) => chart && chart.resize());
      if (this.map) {
        this.map.invalidateSize();
      }
    },
    crossEdgeCount() {
      return (this.dashboard.edges || []).reduce(
        (count, edge) => count + (edge && edge.is_cross_community ? 1 : 0),
        0
      );
    },
  },
});

if (typeof ElementPlus !== 'undefined') {
  const locale = typeof ElementPlusLocaleZhCn !== 'undefined' ? ElementPlusLocaleZhCn : null;
  app.use(ElementPlus, { locale });
  
  if (typeof ElementPlusIconsVue !== 'undefined') {
    const iconModule =
      ElementPlusIconsVue && ElementPlusIconsVue.default && typeof ElementPlusIconsVue.default === "object"
        ? ElementPlusIconsVue.default
        : ElementPlusIconsVue;

    for (const [key, component] of Object.entries(iconModule || {})) {
      if (key === "default" || key === "__esModule") continue;
      const isComponent = component && (typeof component === "object" || typeof component === "function");
      if (!isComponent) continue;
      if (!("render" in component) && !("setup" in component)) continue;
      app.component(key, component);
    }
  }
}

app.mount("#app");
