const path = require('path');
const gulp = require('gulp');
const exec = require('child_process').exec;
const fs = require("fs");
const fsp = fs.promises;
const concat = require('gulp-concat');
const connect = require('gulp-connect');
const bodyParser = require('body-parser');
const multer = require('multer');
const { watch } = require('gulp');

const { createExamplesPage } = require("./src/tools/create_potree_page");
const { createGithubPage } = require("./src/tools/create_github_page");
const { createIconsPage } = require("./src/tools/create_icons_page");

let paths = {
    laslaz: [
        "build/workers/laslaz-worker.js",
        "build/workers/lasdecoder-worker.js",
    ],
    html: [
        "src/viewer/potree.css",
        "src/viewer/sidebar.html",
        "src/viewer/profile.html"
    ],
    resources: [
        "resources/**/*"
    ]
};

let workers = {
    "LASLAZWorker": [
        "libs/plasio/workers/laz-perf.js",
        "libs/plasio/workers/laz-loader-worker.js"
    ],
    "LASDecoderWorker": [
        "src/workers/LASDecoderWorker.js"
    ],
    "EptLaszipDecoderWorker": [
        "libs/copc/index.js",
        "src/workers/EptLaszipDecoderWorker.js"
    ],
    "EptBinaryDecoderWorker": [
        "libs/ept/ParseBuffer.js",
        "src/workers/EptBinaryDecoderWorker.js"
    ],
    "EptZstandardDecoderWorker": [
        "src/workers/EptZstandardDecoder_preamble.js",
        'libs/zstd-codec/bundle.js',
        "libs/ept/ParseBuffer.js",
        "src/workers/EptZstandardDecoderWorker.js"
    ]
};

// these libs are lazily loaded
// in order for the lazy loader to find them, independent of the path of the html file,
// we package them together with potree
let lazyLibs = {
    "geopackage": "libs/geopackage",
    "sql.js": "libs/sql.js"
};

let shaders = [
    "src/materials/shaders/pointcloud.vs",
    "src/materials/shaders/pointcloud.fs",
    "src/materials/shaders/pointcloud_sm.vs",
    "src/materials/shaders/pointcloud_sm.fs",
    "src/materials/shaders/normalize.vs",
    "src/materials/shaders/normalize.fs",
    "src/materials/shaders/normalize_and_edl.fs",
    "src/materials/shaders/edl.vs",
    "src/materials/shaders/edl.fs",
    "src/materials/shaders/blur.vs",
    "src/materials/shaders/blur.fs",
];

// Middleware to log incoming requests
const logRequest = (req, _res, next) => {
    console.log(`Received ${req.method} request for ${req.url}`);
    next();
};

const upload = multer({ dest: 'uploads/' });

let lastExecutionTime = 0;
const rateLimitMiddleware = (req, res, next) => {
    const now = Date.now();
    if (now - lastExecutionTime < 1000) {  // 1000 ms = 1 second
        res.writeHead(429, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Too many requests, please try again later.' }));
        return;
    }
    lastExecutionTime = now;
    next();
};

gulp.task('webserver', gulp.series(async function () {
    connect.server({
        port: 1234,
        https: false,
        middleware: function (_connect, _opt) {
            return [
                logRequest,
                bodyParser.json(),
                bodyParser.raw({ type: 'application/octet-stream', limit: '10mb' }),
                rateLimitMiddleware,
                async function (req, res, next) {
                    if (req.method === 'POST' && req.url === '/save-shapefile-component') {
                        const filename = req.headers['x-filename'];
                        const treeId = req.headers['x-treeid'];
                        const dir = path.join(__dirname, 'outputs', treeId);
                        const filePath = path.join(dir, filename);

                        try {
                            await fsp.mkdir(dir, { recursive: true });
                            await fsp.access(dir, fs.constants.W_OK);
                            await fsp.writeFile(filePath, req.body);

                            console.log('Shapefile component saved successfully:', filePath);
                            res.writeHead(200, {'Content-Type': 'application/json'});
                            res.end(JSON.stringify({ message: 'Shapefile component saved successfully' }));
                        } catch (err) {
                            console.error('Server error:', err);
                            res.writeHead(500, {'Content-Type': 'application/json'});
                            res.end(JSON.stringify({ error: 'Server error', details: err.message }));
                        }
                    } else if (req.method === 'POST' && req.url === '/save-geojson') {
                        upload.single('file')(req, res, async (err) => {
                            if (err) {
                                console.error('Multer error:', err);
                                res.writeHead(500, { 'Content-Type': 'application/json' });
                                res.end(JSON.stringify({ error: 'Multer error', details: err.message }));
                                return;
                            }
                            const treeId = req.headers['x-treeid'];
                            const file = req.file;
                            const destDir = path.join(__dirname, 'outputs', treeId);

                            try {
                                await fsp.mkdir(destDir, { recursive: true });

                                // Move the file to the destination directory
                                const destPath = path.join(destDir, `${treeId}_new_height_measurement.geojson`);
                                await fsp.rename(file.path, destPath);

                                console.log('GeoJSON file saved successfully:', destPath);

                                // Trigger the Python script
                                exec(`python3 src/python/scripts/filehandlers/shapeconverter.py ${destPath}`, (error, stdout, stderr) => {
                                    if (error) {
                                        console.error('Error executing Python script:', error);
                                        res.writeHead(500, { 'Content-Type': 'application/json' });
                                        res.end(JSON.stringify({ error: 'Error executing Python script' }));
                                        return;
                                    }
                                    console.log('Python script executed successfully:', stdout, stderr);
                                    res.writeHead(200, { 'Content-Type': 'application/json' });
                                    res.end(JSON.stringify({ message: 'GeoJSON file saved and Python script executed successfully' }));
                                });
                            } catch (error) {
                                console.error('Server error:', error);
                                res.writeHead(500, { 'Content-Type': 'application/json' });
                                res.end(JSON.stringify({ error: 'Server error', details: error.message }));
                            }
                        });
                    } else if (req.method === 'POST' && req.url === '/update-json') {
                        console.log("POST request received with data:", req.body);
                        const { treeId, data } = req.body;

                        const dir = path.join(__dirname, 'outputs', treeId);
                        const filePath = path.join(dir, `${treeId}_measurements.json`);

                        try {
                            await fsp.mkdir(dir, { recursive: true });
                            await fsp.access(dir, fs.constants.W_OK);
                            await fsp.writeFile(filePath, JSON.stringify(data, null, 2));

                            console.log('File updated successfully:', filePath);
                            res.writeHead(200, {'Content-Type': 'application/json'});
                            res.end(JSON.stringify({ message: 'File updated successfully' }));
                        } catch (err) {
                            console.error('Server error:', err);
                            res.writeHead(500, {'Content-Type': 'application/json'});
                            res.end(JSON.stringify({ error: 'Server error', details: err.message }));
                        }
                    } else if (req.method === 'POST' && req.url === '/save-shapefile') {
                        console.log("POST request received to save shapefile:", req.body);
                        const { path: relativePath, data } = req.body;

                        const filePath = path.join(__dirname, relativePath);

                        try {
                            await fsp.mkdir(path.dirname(filePath), { recursive: true });
                            await fsp.writeFile(filePath, JSON.stringify(data, null, 2));
                            console.log('Shapefile saved successfully:', filePath);
                            res.writeHead(200, {'Content-Type': 'application/json'});
                            res.end(JSON.stringify({ message: 'Shapefile saved successfully' }));
                        } catch (err) {
                            console.error('Server error:', err);
                            res.writeHead(500, {'Content-Type': 'application/json'});
                            res.end(JSON.stringify({ error: 'Server error', details: err.message }));
                        }
                    } else {
                        next();
                    }
                }
            ];
        }
    });
}));

gulp.task('examples_page', async function (done) {
    await Promise.all([
        createExamplesPage(),
        createGithubPage(),
    ]);

    done();
});

gulp.task('icons_viewer', async function (done) {
    await createIconsPage();

    done();
});

gulp.task('test', async function () {
    console.log("Test task executed");
});

gulp.task("workers", async function (done) {
    for (let workerName of Object.keys(workers)) {
        gulp.src(workers[workerName])
            .pipe(concat(`${workerName}.js`))
            .pipe(gulp.dest('build/potree/workers'));
    }

    gulp.src('./libs/copc/laz-perf.wasm')
        .pipe(gulp.dest('./build/potree/workers'));

    done();
});

gulp.task("lazylibs", async function (done) {
    for (let libname of Object.keys(lazyLibs)) {
        const libpath = lazyLibs[libname];

        gulp.src([`${libpath}/**/*`])
            .pipe(gulp.dest(`build/potree/lazylibs/${libname}`));
    }
    done();
});

gulp.task("shaders", async function () {
    const components = [
        "let Shaders = {};"
    ];

    for (let file of shaders) {
        const filename = path.basename(file);
        const content = await fsp.readFile(file);
        const prep = `Shaders["${filename}"] = \`${content}\``;
        components.push(prep);
    }

    components.push("export {Shaders};");

    const content = components.join("\n\n");
    const targetPath = `./build/shaders/shaders.js`;

    if (!fs.existsSync("build/shaders")) {
        fs.mkdirSync("build/shaders");
    }
    fs.writeFileSync(targetPath, content, { flag: "w" });
});

gulp.task('build',
    gulp.series(
        gulp.parallel("workers", "lazylibs", "shaders", "icons_viewer", "examples_page"),
        async function (done) {
            gulp.src(paths.html).pipe(gulp.dest('build/potree'));
            gulp.src(paths.resources).pipe(gulp.dest('build/potree/resources'));
            gulp.src(["LICENSE"]).pipe(gulp.dest('build/potree'));
            done();
        }
    )
);

gulp.task("pack", async function () {
    exec('rollup -c', function (err, stdout, stderr) {
        console.log(stdout);
        console.log(stderr);
    });
});

gulp.task('watch', gulp.parallel("build", "pack", "webserver", async function () {
    let watchlist = [
        'src/**/*.js',
        'src/**/**/*.js',
        'src/**/*.css',
        'src/**/*.html',
        'src/**/*.vs',
        'src/**/*.fs',
        'resources/**/*',
        'examples//**/*.json',
        '!resources/icons/index.html',
    ];

    watch(watchlist, gulp.series("build", "pack"));
}));
