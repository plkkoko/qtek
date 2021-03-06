# ############################################
# fbx to glTF converter
# glTF spec : https://github.com/KhronosGroup/glTF
# fbx version 2018.1.1
# TODO: support python2.7
# http://github.com/pissang/
# ############################################
import sys, struct, json, os.path, math, argparse

try:
    from FbxCommon import *
except ImportError:
    import platform
    msg = 'You need to copy the content in compatible subfolder under /lib/python<version> into your python install folder such as '
    if platform.system() == 'Windows' or platform.system() == 'Microsoft':
        msg += '"Python26/Lib/site-packages"'
    elif platform.system() == 'Linux':
        msg += '"/usr/local/lib/python3.3/site-packages"'
    elif platform.system() == 'Darwin':
        msg += '"/Library/Frameworks/Python.framework/Versions/3.3/lib/python3.3/site-packages"'
    msg += ' folder.'
    print(msg)
    sys.exit(1)

lib_materials = {}
lib_techniques = {}

lib_images = {}
lib_samplers = {}
lib_textures = {}

# attributes, indices, anim_parameters will be merged in accessors
lib_attributes = {}
lib_indices = {}
lib_parameters = {}
lib_accessors = {}

lib_buffer_views = {}
lib_buffers = {}

lib_lights = {}
lib_cameras = {}
lib_meshes = {}

lib_nodes = {}
lib_scenes = {}

lib_skins = {}
lib_joints = {}

lib_animations = {}

# Only python 3 support bytearray ?
# http://dabeaz.blogspot.jp/2010/01/few-useful-bytearray-tricks.html
attributeBuffer = bytearray()
indicesBuffer = bytearray()
invBindMatricesBuffer = bytearray()
animationBuffer = bytearray()

fbxNodes = {};

GL_RGBA = 0x1908
GL_FLOAT = 0x1406
GL_UNSIGNED_BYTE = 0x1401
GL_UNSIGNED_SHORT = 0x1403
GL_INT = 0x1404
GL_UNSIGNED_INT = 0x1405

GL_REPEAT = 0x2901
GL_FLOAT_VEC2 = 0x8B50
GL_FLOAT_VEC3 = 0x8B51
GL_FLOAT_VEC4 = 0x8B52
GL_TEXTURE_2D = 0x0DE1
GL_TEXTURE_CUBE_MAP = 0x8513
GL_REPEAT = 0x2901
GL_CLAMP_TO_EDGE = 0x812F
GL_NEAREST = 0x2600
GL_LINEAR = 0x2601
GL_NEAREST_MIPMAP_NEAREST = 0x2700
GL_LINEAR_MIPMAP_NEAREST = 0x2701
GL_NEAREST_MIPMAP_LINEAR = 0x2702
GL_LINEAR_MIPMAP_LINEAR = 0x2703

GL_ARRAY_BUFFER = 0x8892
GL_ELEMENT_ARRAY_BUFFER = 0x8893

_id = 0
def GetId():
    global _id
    _id = _id + 1
    return _id

def CreateAccessorBuffer(pList, pType, pStride, minMax = False):
    lGLTFAcessor = {}

    lType = '<' + pType * pStride
    lData = []

    if minMax:
        if len(pList) > 0:
            if pStride == 1:
                lMin = pList[0]
                lMax = pList[0]
            else:
                lMin = list(pList[0])
                lMax = list(pList[0])
        else:
            lMax = [0] * pStride
            lMin = [0] * pStride
        lRange = range(pStride)
    #TODO: Other method to write binary buffer ?
    for item in pList:
        if pStride == 1:
            lData.append(struct.pack(lType, item))
        elif pStride == 2:
            lData.append(struct.pack(lType, item[0], item[1]))
        elif pStride == 3:
            lData.append(struct.pack(lType, item[0], item[1], item[2]))
        elif pStride == 4:
            lData.append(struct.pack(lType, item[0], item[1], item[2], item[3]))
        if minMax:
            if pStride == 1:
                lMin = min(lMin, item)
                lMax = max(lMin, item)
            else:
                for i in lRange:
                    lMin[i] = min(lMin[i], item[i])
                    lMax[i] = max(lMax[i], item[i])

    if pType == 'f':
        lByteStride = pStride * 4
        if pStride == 1:
            lGLTFAcessor['type'] = GL_FLOAT
        elif pStride == 2:
            lGLTFAcessor['type'] = GL_FLOAT_VEC2
        elif pStride == 3:
            lGLTFAcessor['type'] = GL_FLOAT_VEC3
        elif pStride == 4:
            lGLTFAcessor['type'] = GL_FLOAT_VEC4
    # Unsigned Int
    elif pType == 'I':
        lByteStride = pStride * 4
        lGLTFAcessor['type'] = GL_UNSIGNED_INT

    # Unsigned Short
    elif pType == 'H':
        lByteStride = pStride * 2
        lGLTFAcessor['type'] = GL_UNSIGNED_SHORT

    lGLTFAcessor['byteOffset'] = 0
    lGLTFAcessor['byteStride'] = lByteStride
    lGLTFAcessor['count'] = len(pList)

    if minMax:
        lGLTFAcessor['max'] = lMax
        lGLTFAcessor['min'] = lMin

    return b''.join(lData), lGLTFAcessor


def CreateAttributeBuffer(pList, pType, pStride):
    lData, lGLTFAttribute = CreateAccessorBuffer(pList, pType, pStride, True)
    lGLTFAttribute['byteOffset'] = len(attributeBuffer)
    attributeBuffer.extend(lData)
    lKey = 'attrbute_' + str(GetId())
    lib_attributes[lKey] = lGLTFAttribute
    return lKey


def CreateIndicesBuffer(pList, pType):
    lData, lGLTFIndices = CreateAccessorBuffer(pList, pType, 1, False)
    lGLTFIndices['byteOffset'] = len(indicesBuffer)
    indicesBuffer.extend(lData)
    lKey = 'indices_' + str(GetId())
    lib_indices[lKey] = lGLTFIndices
    lGLTFIndices.pop('byteStride')
    return lKey

def CreateAnimationBuffer(pList, pType, pStride):
    lData, lGLTFParameter = CreateAccessorBuffer(pList, pType, pStride, False)
    lGLTFParameter['byteOffset'] = len(animationBuffer)
    animationBuffer.extend(lData)
    lKey = 'acc_' + str(GetId())
    lib_parameters[lKey] = lGLTFParameter
    lGLTFParameter.pop('byteStride')
    return lKey

def QuaternionToAxisAngle(pQuat):
    w = pQuat[3]
    if (w == 1):
        return [1, 0, 0, 0]

    divider = 1 / math.sqrt((1 - w * w))
    angle = 2 * math.acos(w)
    x = pQuat[0] * divider
    y = pQuat[1] * divider
    z = pQuat[2] * divider

    return [x, y, z, angle]

# PENDING : Hash mechanism may be different from COLLADA2GLTF
# TODO Cull face
# TODO Blending equation and function
def HashTechnique(pMaterial):
    if (pMaterial.ShadingModel.Get() == 'unknown'):
        return ''

    lHashStr = []
    # Is Transparent
    lHashStr.append(str(pMaterial.TransparencyFactor.Get() > 0))
    # Lambert or Phong
    lHashStr.append(str(pMaterial.ShadingModel.Get()))
    # If enable diffuse map
    lHashStr.append(str(pMaterial.Diffuse.GetSrcObjectCount() > 0))
    # If enable normal map
    lHashStr.append(str(pMaterial.NormalMap.GetSrcObjectCount() > 0))
    lHashStr.append(str(pMaterial.Bump.GetSrcObjectCount() > 0))
    # If enable alpha map
    lHashStr.append(str(pMaterial.TransparentColor.GetSrcObjectCount() > 0))

    if pMaterial.ShadingModel.Get() == 'Phong':
        # If enable specular map
        lHashStr.append(str(pMaterial.Specular.GetSrcObjectCount() > 0))
        # If enable environment map
        lHashStr.append(str(pMaterial.Reflection.GetSrcObjectCount() > 0))

    return ''.join(lHashStr)

_techniqueHashMap = {}
def CreateTechnique(pMaterial):
    if pMaterial.ShadingModel.Get() == 'unknown':
        print('Shading model of ' + pMaterial.GetName() + ' is unknown')
        lHashKey = 'technique_unknown'
    else:
        lHashKey = HashTechnique(pMaterial)
        if lHashKey in _techniqueHashMap:
            return _techniqueHashMap[lHashKey]

    lTechniqueName = 'technique_' + str(len(lib_techniques.keys()))
    _techniqueHashMap[lHashKey] = lTechniqueName
    # PENDING : Default shader ?
    # TODO Multiple pass ?
    lGLTFTechnique = {
        'parameters' : {},
        'pass' : 'defaultPass',
        'passes' : {
            'defaultPass' : {
                'instanceProgram' : {
                    'attributes' : {},
                    'program' : '',
                    'uniforms' : {}
                },
                'states' : {
                    # TODO CULL FACE
                    'cullFaceEnable' : False,
                    'depthTestEnable' : True,
                    'depthMask' : True,
                    'blendEnable' : False
                }
            }
        }
    }
    # Enable blend
    try :
        # Old fbx version transparency is 0 if object is opaque
        if pMaterial.TransparencyFactor.Get() < 1 and pMaterial.TransparencyFactor.Get() > 0:
            lStates = lGLTFTechnique['passes']['defaultPass']['states']
            lStates['blendEnable'] = True
            lStates['blendEquation'] = 'FUNC_ADD'
            lStates['blendFunc'] = {
                'dfactor' : 'ONE_MINUS_SRC_ALPHA',
                'sfactor' : 'SRC_ALPHA'
            }
            lStates['depthMask'] = False
            lStates['depthTestEnable'] = True

        lib_techniques[lTechniqueName] = lGLTFTechnique
    except:
        pass

    return lTechniqueName

#PENDING Use base name as key ?
def CreateImage(pPath):
    lImageKey = [name for name in lib_images.keys() if lib_images[name]['path'] == pPath]
    if len(lImageKey):
        return lImageKey[0]

    lImageKey = 'image_' + str(len(lib_images.keys()))
    lib_images[lImageKey] = {
        'path' : pPath
    }
    return lImageKey

def HashSampler(pTexture):
    lHashStr = []
    # Wrap S
    lHashStr.append(str(pTexture.WrapModeU.Get()))
    # Wrap T
    lHashStr.append(str(pTexture.WrapModeV.Get()))
    return ' '.join(lHashStr)

def ConvertWrapMode(pWrap):
    if pWrap == FbxTexture.eRepeat:
        return GL_REPEAT
    elif pWrap == FbxTexture.eClamp:
        return GL_CLAMP_TO_EDGE

_samplerHashMap = {}
def CreateSampler(pTexture):
    lHashKey = HashSampler(pTexture)
    if lHashKey in _samplerHashMap:
        return _samplerHashMap[lHashKey]
    else:
        lSamplerName = 'sampler_' + str(len(lib_samplers.keys()))
        lib_samplers[lSamplerName] = {
            'wrapS' : ConvertWrapMode(pTexture.WrapModeU.Get()),
            'wrapT' : ConvertWrapMode(pTexture.WrapModeV.Get()),
            # Texture filter in fbx ?
            'minFilter' : GL_LINEAR_MIPMAP_LINEAR,
            'magFilter' : GL_LINEAR
        }
        _samplerHashMap[lHashKey] = lSamplerName
        return lSamplerName

_textureHashMap = {}
_repeatedTextureCount = {}
def CreateTexture(pProperty):
    lTextureList = []

    lFileTextures = []
    lLayeredTextureCount = pProperty.GetSrcObjectCount(FbxCriteria.ObjectType(FbxLayeredTexture.ClassId))
    if lLayeredTextureCount > 0:
        for i in range(lLayeredTextureCount):
            lLayeredTexture = pProperty.GetSrcObject(FbxCriteria.ObjectType(FbxLayeredTexture.ClassId), i)
            for j in range(lLayeredTexture.GetSrcObjectCount(FbxCriteria.ObjectType(FbxTexture.ClassId))):
                lTexture = lLayeredTexture.GetSrcObject(FbxCriteria.ObjectType(FbxTexture.ClassId), j)
                if lTexture and lTexture.__class__ == FbxFileTexture:
                    lFileTextures.append(lTexture)
        pass
    else:
        lTextureCount = pProperty.GetSrcObjectCount(FbxCriteria.ObjectType(FbxTexture.ClassId))
        for t in range(lTextureCount):
            lTexture = pProperty.GetSrcObject(FbxCriteria.ObjectType(FbxTexture.ClassId), t)
            if lTexture and lTexture.__class__ == FbxFileTexture:
                lFileTextures.append(lTexture)

    for lTexture in lFileTextures:
        lImageName = CreateImage(lTexture.GetFileName())
        lSamplerName = CreateSampler(lTexture)
        lHashKey = (lImageName, lSamplerName)
        if lHashKey in _textureHashMap:
            lTextureList.append(_textureHashMap[lHashKey])
        else:
            lTextureName = lTexture.GetName()
            # Map name may be repeat
            while lTextureName in lib_textures:
                if not lTextureName in _repeatedTextureCount:
                    _repeatedTextureCount[lTextureName] = 0
                else:
                    _repeatedTextureCount[lTextureName] += 1
                lTextureName = lTextureName + '_' + str(_repeatedTextureCount[lTextureName])
            lib_textures[lTextureName] ={
                'format' : GL_RGBA,
                'internalFormat' : GL_RGBA,
                'sampler' : lSamplerName,
                'source' : lImageName,
                # TODO Texture Cube
                'target' : GL_TEXTURE_2D
            }
            _textureHashMap[lHashKey] = lTextureName
            lTextureList.append(lTextureName)
    # PENDING Return the first texture ?
    if len(lTextureList) > 0:
        return lTextureList[0]
    else:
        return None

_materialHashMap = {}
_duplicateMaterialCount = {}
def ConvertMaterial(pMaterial):
    lMaterialName = pMaterial.GetName()

    lGLTFMaterial = {"name" : lMaterialName}

    # PENDING Multiple techniques ?
    lTechniqueName = CreateTechnique(pMaterial)
    lGLTFMaterial["instanceTechnique"] = {
        "technique" : lTechniqueName,
        "values" : {}
    }
    lValues = lGLTFMaterial['instanceTechnique']['values']

    lShading = pMaterial.ShadingModel.Get()

    if (lShading == 'unknown'):
        lib_materials[lMaterialName] = lGLTFMaterial
        return lMaterialName

    lValues['ambient'] = list(pMaterial.Ambient.Get())
    lValues['emission'] = list(pMaterial.Emissive.Get())

    if pMaterial.TransparencyFactor.Get() < 1:
        lValues['transparency'] = pMaterial.TransparencyFactor.Get()
        # Old fbx version transparency is 0 if object is opaque
        if (lValues['transparency'] == 0):
            lValues['transparency'] = 1

    # Use diffuse map
    # TODO Diffuse Factor ?
    if pMaterial.Diffuse.GetSrcObjectCount() > 0:
        lTextureName = CreateTexture(pMaterial.Diffuse)
        if not lTextureName == None:
            lValues['diffuse'] = lTextureName
    else:
        lValues['diffuse'] = list(pMaterial.Diffuse.Get())

    if pMaterial.Bump.GetSrcObjectCount() > 0:
        # TODO 3dsmax use the normal map as bump map ?
        lTextureName = CreateTexture(pMaterial.Bump)
        if not lTextureName == None:
            lValues['normalMap'] = lTextureName

    if pMaterial.NormalMap.GetSrcObjectCount() > 0:
        lTextureName = CreateTexture(pMaterial.NormalMap)
        if not lTextureName == None:
            lValues['normalMap'] = lTextureName

    if lShading == 'phong':
        lValues['shininess'] = pMaterial.Shininess.Get();
        # Use specular map
        # TODO Specular Factor ?
        if pMaterial.Specular.GetSrcObjectCount() > 0:
            pass
        else:
            lValues['specular'] = list(pMaterial.Specular.Get())

    # Material name of different material may be same after SplitMeshByMaterial
    lHashKey = [lMaterialName]
    for lKey in lValues.keys():
        lValue = lValues[lKey];
        lHashKey.append(lKey)
        lHashKey.append(str(lValue))
    lHashKey = tuple(lHashKey)
    if lHashKey in _materialHashMap:
        return _materialHashMap[lHashKey];

    while lMaterialName in lib_materials:
        if not lMaterialName in _duplicateMaterialCount:
            _duplicateMaterialCount[lMaterialName] = 0
        else:
            _duplicateMaterialCount[lMaterialName] += 1
        lMaterialName = lMaterialName + '_' + str(_duplicateMaterialCount[lMaterialName])
    _materialHashMap[lHashKey] =  lMaterialName

    lGLTFMaterial['name'] = lMaterialName
    lib_materials[lMaterialName] = lGLTFMaterial
    return lMaterialName

def ConvertVertexLayer(pMesh, pLayer, pOutput):
    lMappingMode = pLayer.GetMappingMode()
    lReferenceMode = pLayer.GetReferenceMode()

    if lMappingMode == FbxLayerElement.eByControlPoint:
        if lReferenceMode == FbxLayerElement.eDirect:
            for vec in pLayer.GetDirectArray():
                pOutput.append(vec)
        elif lReferenceMode == FbxLayerElement.eIndexToDirect:
            lIndexArray = pLayer.GetIndexArray()
            lDirectArray = pLayer.GetDirectArray()
            for idx in lIndexArray:
                pOutput.append(lDirectArray.GetAt(idx))

        return False
    elif lMappingMode == FbxLayerElement.eByPolygonVertex:
        if lReferenceMode == FbxLayerElement.eDirect:
            for vec in pLayer.GetDirectArray():
                pOutput.append(vec)
        # Need to split vertex
        # TODO: Normal per vertex will still have ByPolygonVertex in COLLADA
        elif lReferenceMode == FbxLayerElement.eIndexToDirect:
            lIndexArray = pLayer.GetIndexArray()
            lDirectArray = pLayer.GetDirectArray()
            for idx in lIndexArray:
                pOutput.append(lDirectArray.GetAt(idx))
        else:
            print("Unsupported mapping mode " + lMappingMode)

        return True

def CreateSkin():
    lSkinName = "skin_" + str(len(lib_skins.keys()))
    # https://github.com/KhronosGroup/glTF/issues/100
    lib_skins[lSkinName] = {
        # 'bindShapeMatrix' : [],
        'inverseBindMatrices' : {
            "count" : 0,
            "byteOffset" : len(invBindMatricesBuffer),
            "type" : GL_FLOAT
        },
        'joints' : [],
    }

    return lSkinName

_defaultMaterialName = 'DEFAULT_MAT_'
_defaultMaterialIndex = 0

def ConvertMesh(pScene, pMesh, pNode, pSkin, pClusters):

    global _defaultMaterialIndex;

    lGLTFPrimitive = {}
    lPositions = []
    lNormals = []
    lTexcoords = []
    lTexcoords2 = []
    lIndices = []

    lWeights = []
    lJoints = []
    # Count joint number of each vertex
    lJointCounts = []

    # Only consider layer 0
    lLayer = pMesh.GetLayer(0)
    # Uv of lightmap on layer 1
    # PENDING Uv2 always on layer 1?
    lLayer2 = pMesh.GetLayer(1)

    if lLayer:
        ## Handle material
        lLayerMaterial = lLayer.GetMaterials()
        lMaterial = None;
        if not lLayerMaterial:
            print("Mesh " + GetNodeNameWithoutDuplication(pNode) + " doesn't have material")
            lMaterial = FbxSurfacePhong.Create(pScene, _defaultMaterialName + str(_defaultMaterialIndex))
            _defaultMaterialIndex += 1;
        else:
            # Mapping Mode of material must be eAllSame
            # Because the mesh has been splitted by material
            idx = lLayerMaterial.GetIndexArray()[0];
            lMaterial = pNode.GetMaterial(idx)
        lMaterialKey = ConvertMaterial(lMaterial)
        lGLTFPrimitive["material"] = lMaterialKey

        lNormalSplitted = False
        lUvSplitted = False
        lUv2Splitted = False
        ## Handle normals
        lLayerNormal = lLayer.GetNormals()
        if lLayerNormal:
            lNormalSplitted = ConvertVertexLayer(pMesh, lLayerNormal, lNormals)

        ## Handle uvs
        lLayerUV = lLayer.GetUVs()

        lLayer2Uv = None

        if lLayerUV:
            lUvSplitted = ConvertVertexLayer(pMesh, lLayerUV, lTexcoords)

        if lLayer2:
            lLayer2Uv = lLayer2.GetUVs()
            if lLayer2Uv:
                lUv2Splitted = ConvertVertexLayer(pMesh, lLayer2Uv, lTexcoords2)

        hasSkin = False
        moreThanFourJoints = False
        lMaxJointCount = 0
        ## Handle Skinning data
        if (pMesh.GetDeformerCount(FbxDeformer.eSkin) > 0):
            hasSkin = True
            lControlPointsCount = pMesh.GetControlPointsCount()
            for i in range(lControlPointsCount):
                lWeights.append([0, 0, 0, 0])
                lJoints.append([-1, -1, -1, -1])
                lJointCounts.append(0)

            for i in range(pMesh.GetDeformerCount(FbxDeformer.eSkin)):
                lDeformer = pMesh.GetDeformer(i, FbxDeformer.eSkin)

                for i2 in range(lDeformer.GetClusterCount()):
                    lCluster = lDeformer.GetCluster(i2)
                    lNode = lCluster.GetLink()
                    lJointIndex = -1
                    lNodeName = GetNodeNameWithoutDuplication(lNode)
                    if not lNodeName in pSkin['joints']:
                        lJointIndex = len(pSkin['joints'])
                        pSkin['joints'].append(lNodeName)

                        pClusters[lNodeName] = lCluster
                    else:
                        lJointIndex = pSkin['joints'].index(lNodeName)

                    lControlPointIndices = lCluster.GetControlPointIndices()
                    lControlPointWeights = lCluster.GetControlPointWeights()

                    for i3 in range(lCluster.GetControlPointIndicesCount()):
                        lControlPointIndex = lControlPointIndices[i3]
                        lControlPointWeight = lControlPointWeights[i3]
                        lJointCount = lJointCounts[lControlPointIndex]

                        # At most binding four joint per vertex
                        if lJointCount <= 3:
                            # Joint index
                            lJoints[lControlPointIndex][lJointCount] = lJointIndex
                            lWeights[lControlPointIndex][lJointCount] = lControlPointWeight
                        else:
                            moreThanFourJoints = True
                            # More than four joints, replace joint of minimum Weight
                            lMinW, lMinIdx = min( (lWeights[lControlPointIndex][i], i) for i in range(len(lWeights[lControlPointIndex])) )
                            lJoints[lControlPointIndex][lMinIdx] = lJointIndex
                            lWeights[lControlPointIndex][lMinIdx] = lControlPointWeight
                            lMaxJointCount = max(lMaxJointCount, lJointIndex)
                        lJointCounts[lControlPointIndex] += 1

        if moreThanFourJoints:
            print('More than 4 joints (%d joints) bound to per vertex in %s. ' %(lMaxJointCount, GetNodeNameWithoutDuplication(pNode)))

        # Weight is FLOAT_3 because it is normalized
        for i in range(len(lWeights)):
            lWeights[i] = lWeights[i][:3]

        if lNormalSplitted or lUvSplitted or lUv2Splitted:
            lCount = 0
            lVertexCount = 0
            lNormalsTmp = []
            lTexcoordsTmp = []
            lTexcoords2Tmp = []
            lJointsTmp = []
            lWeightsTmp = []
            lVertexMap = {}

            for idx in pMesh.GetPolygonVertices():
                lPosition = pMesh.GetControlPointAt(idx)
                if not lNormalSplitted:
                    # Split normal data
                    lNormal = lNormals[idx]
                else:
                    lNormal = lNormals[lCount]

                if lLayerUV:
                    if not lUvSplitted:
                        lTexcoord = lTexcoords[idx]
                    else:
                        lTexcoord = lTexcoords[lCount]

                if lLayer2Uv:
                    if not lUv2Splitted:
                        lTexcoord = lTexcoords2[idx]
                    else:
                        lTexcoord2 = lTexcoords2[lCount]

                lCount += 1

                #Compress vertex, hashed with position and normal
                if lLayer2Uv:
                    if lLayer2Uv:
                        lKey = (lPosition[0], lPosition[1], lPosition[2], lNormal[0], lNormal[1], lNormal[2], lTexcoord[0], lTexcoord[1], lTexcoord2[0], lTexcoord2[1])
                    else:
                        lKey = (lPosition[0], lPosition[1], lPosition[2], lNormal[0], lNormal[1], lNormal[2], lTexcoord2[0], lTexcoord2[1])
                elif lLayerUV:
                    lKey = (lPosition[0], lPosition[1], lPosition[2], lNormal[0], lNormal[1], lNormal[2], lTexcoord[0], lTexcoord[1])
                else:
                    lKey = (lPosition[0], lPosition[1], lPosition[2], lNormal[0], lNormal[1], lNormal[2])

                if lKey in lVertexMap:
                    lIndices.append(lVertexMap[lKey])
                else:
                    lPositions.append(lPosition)
                    lNormalsTmp.append(lNormal)

                    if lLayerUV:
                        lTexcoordsTmp.append(lTexcoord)

                    if lLayer2Uv:
                        lTexcoords2Tmp.append(lTexcoord2)

                    if hasSkin:
                        lWeightsTmp.append(lWeights[idx])
                        lJointsTmp.append(lJoints[idx])
                    lIndices.append(lVertexCount)
                    lVertexMap[lKey] = lVertexCount
                    lVertexCount += 1

            lNormals = lNormalsTmp
            lTexcoords = lTexcoordsTmp
            lTexcoords2 = lTexcoords2Tmp

            if hasSkin:
                lWeights = lWeightsTmp
                lJoints = lJointsTmp
        else:
            lIndices = pMesh.GetPolygonVertices()
            lPositions = pMesh.GetControlPoints()

        lGLTFPrimitive['attributes'] = {}
        lGLTFPrimitive['attributes']['POSITION'] = CreateAttributeBuffer(lPositions, 'f', 3)
        if not lLayerNormal == None:
            lGLTFPrimitive['attributes']['NORMAL'] = CreateAttributeBuffer(lNormals, 'f', 3)
        if lLayerUV:
            lGLTFPrimitive['attributes']['TEXCOORD_0'] = CreateAttributeBuffer(lTexcoords, 'f', 2)
        if lLayer2Uv:
            lGLTFPrimitive['attributes']['TEXCOORD_1'] = CreateAttributeBuffer(lTexcoords2, 'f', 2)
        if hasSkin:
            # PENDING Joint indices use other data type ?
            lGLTFPrimitive['attributes']['JOINT'] = CreateAttributeBuffer(lJoints, 'f', 4)
            lGLTFPrimitive['attributes']['WEIGHT'] = CreateAttributeBuffer(lWeights, 'f', 3)

        if len(lPositions) >= 0xffff:
            #Use unsigned int in element indices
            lIndicesType = 'I'
        else:
            lIndicesType = 'H'
        lGLTFPrimitive['indices'] = CreateIndicesBuffer(lIndices, lIndicesType)

        return lGLTFPrimitive
    else:
        return None

def ConvertLight(pLight):
    lGLTFLight = {}
    # In fbx light's name is empty ?
    if GetNodeNameWithoutDuplication(pLight) == "":
        lLightName = "light_" + str(len(lib_lights.keys()))
    else:
        lLightName = GetNodeNameWithoutDuplication(pLight) + '-light'

    lGLTFLight['id'] = lLightName

    # PENDING Consider Intensity ?
    lightColor = pLight.Color.Get()
    # PENDING Why have a id property here(not name, and camera don't have)
    lLightType = pLight.LightType.Get()
    if lLightType == FbxLight.ePoint:
        lGLTFLight['type'] = 'point'
        lGLTFLight['point'] = {
            'color' : list(lightColor),
            # TODO
            "constantAttenuation": 1,
            "linearAttenuation": 0,
            "quadraticAttenuation": 0.00159997
        }
        pass
    elif lLightType == FbxLight.eDirectional:
        lGLTFLight['type'] = 'directional'
        lGLTFLight['directional'] = {
            'color' : list(lightColor)
        }
    elif lLightType == FbxLight.eSpot:
        lGLTFLight['type'] = 'spot'
        lGLTFLight['spot'] = {
            'color' : list(lightColor),
            # InnerAngle can be zero, so we use outer angle here
            'fallOffAngle' : pLight.OuterAngle.Get(),
            "fallOffExponent": 0.15,
            # TODO
            "constantAttenuation": 1,
            "linearAttenuation": 0,
            "quadraticAttenuation": 0.00159997
        }

    lib_lights[lLightName] = lGLTFLight

    return lLightName

def ConvertCamera(pCamera):
    lGLTFCamera = {}

    if pCamera.ProjectionType.Get() == FbxCamera.ePerspective:
        lGLTFCamera['projection'] = 'perspective'
        lGLTFCamera['xfov'] = pCamera.FieldOfView.Get()
    elif pCamera.ProjectionType.Get() == FbxCamera.eOrthogonal:
        lGLTFCamera['projection'] = 'orthographic'
        # TODO
        lGLTFCamera['xmag'] = 1.0
        lGLTFCamera['ymag'] = 1.0

    lGLTFCamera['znear'] = pCamera.NearPlane.Get()
    lGLTFCamera['zfar'] = pCamera.FarPlane.Get()

    # In fbx camera's name is empty ?
    if GetNodeNameWithoutDuplication(pCamera) == '':
        lCameraName = 'camera_' + str(len(lib_cameras.keys()))
    else:
        lCameraName = GetNodeNameWithoutDuplication(pCamera) + '-camera'
    lib_cameras[lCameraName] = lGLTFCamera
    return lCameraName

_duplicateNodeCount = {}
_nodeNameMap = {}
_exitNodes = {}

def GetNodeNameWithoutDuplication(pNode):
    lNodeName = pNode.GetName()
    if not pNode.GetUniqueID() in _nodeNameMap:
        while lNodeName in _exitNodes:
            if not lNodeName in _duplicateNodeCount:
                _duplicateNodeCount[lNodeName] = 0
            else:
                _duplicateNodeCount[lNodeName] += 1
            lNodeName = lNodeName + '_' + str(_duplicateNodeCount[lNodeName])

        _nodeNameMap[pNode.GetUniqueID()] = lNodeName
        _exitNodes[lNodeName] = True

    return _nodeNameMap[pNode.GetUniqueID()]

def ConvertSceneNode(pScene, pNode, pPoseTime, fbxConverter):
    lGLTFNode = {}
    lNodeName = GetNodeNameWithoutDuplication(pNode)
    lGLTFNode['name'] = lNodeName

    lib_nodes[lNodeName] = lGLTFNode

    # Transform matrix
    m = pNode.EvaluateLocalTransform(pPoseTime)
    lGLTFNode['matrix'] = [
        m[0][0], m[0][1], m[0][2], m[0][3],
        m[1][0], m[1][1], m[1][2], m[1][3],
        m[2][0], m[2][1], m[2][2], m[2][3],
        m[3][0], m[3][1], m[3][2], m[3][3],
    ]

    #PENDING : Triangulate and split all geometry not only the default one ?
    #PENDING : Multiple node use the same mesh ?
    lGeometry = pNode.GetGeometry()
    if not lGeometry == None:
        lMeshKey = lNodeName + '-mesh'
        lMeshName = lGeometry.GetName()
        if lMeshName == '':
            lMeshName = lMeshKey

        lGLTFMesh = lib_meshes[lMeshKey] = {'name' : lMeshName, 'primitives' : []}

        fbxConverter.Triangulate(lGeometry, True)
        # TODO SplitMeshPerMaterial may loss deformer in mesh
        # TODO It will be crashed in some fbx files
        # FBX version 2014.2 seems have fixed it
        if not pNode.GetMesh() == None:
            fbxConverter.SplitMeshPerMaterial(pNode.GetMesh(), True)

        lHasSkin = False
        lGLTFSkin = None
        lClusters = {}
        lSkinName = ''

        # If any attribute of this node have skinning data
        # (Mesh splitted by material may have multiple MeshAttribute in one node)
        for i in range(pNode.GetNodeAttributeCount()):
            lNodeAttribute = pNode.GetNodeAttributeByIndex(i)
            if lNodeAttribute.GetAttributeType() == FbxNodeAttribute.eMesh:
                if (lNodeAttribute.GetDeformerCount(FbxDeformer.eSkin) > 0):
                    lHasSkin = True
        if lHasSkin:
            lSkinName = CreateSkin()
            lGLTFSkin = lib_skins[lSkinName]

        for i in range(pNode.GetNodeAttributeCount()):
            lNodeAttribute = pNode.GetNodeAttributeByIndex(i)
            if lNodeAttribute.GetAttributeType() == FbxNodeAttribute.eMesh:
                lPrimitive = ConvertMesh(pScene, lNodeAttribute, pNode, lGLTFSkin, lClusters)
                if not lPrimitive == None:
                    lGLTFMesh["primitives"].append(lPrimitive)

        if lHasSkin:
            roots = []
            lGLTFNode['instanceSkin'] = {
                'skeletons' : roots,
                'skin' : lSkinName,
                'sources' : [lMeshKey]
            }
            lExtraJoints = []
            # Find Root
            for lJointName in lGLTFSkin['joints']:
                lCluster = lClusters[lJointName]
                lLink = lCluster.GetLink()
                lParent = lLink
                lRootFound = False
                lParentName = GetNodeNameWithoutDuplication(lParent)
                # if lParent == None or not lParent.GetName() in lGLTFSkin['joints']:
                #     if not lParent.GetName() in roots:
                #         roots.append(lLink.GetName())
                while not lParent == None:
                    lSkeleton = lParent.GetSkeleton()
                    if lSkeleton == None:
                        break;

                    # In case some skeleton is not a attached to any vertices(not a cluster)
                    # PENDING
                    if not lParentName in lGLTFSkin['joints'] and not lParentName in lExtraJoints:
                        lExtraJoints.append(lParentName)

                    if lSkeleton.IsSkeletonRoot():
                        lRootFound = True
                        break;
                    lParent = lParent.GetParent()
                    lParentName = GetNodeNameWithoutDuplication(lParent)

                # lSkeletonTypes = ["Root", "Limb", "Limb Node", "Effector"]
                # print(lSkeletonTypes[lSkeleton.GetSkeletonType()])

                if lRootFound:
                    if not lParentName in roots:
                        roots.append(lParentName)
                else:
                    # TODO IsSkeletonRoot not works well, try another way
                    # which do not have a parent or its parent is not in skin
                    lParent = lLink.GetParent()
                    if lParent == None or not GetNodeNameWithoutDuplication(lParent) in lGLTFSkin['joints']:
                        if not GetNodeNameWithoutDuplication(lLink) in roots:
                            roots.append(GetNodeNameWithoutDuplication(lLink))

            # lRootNode = fbxNodes[roots[0]]
            # lRootNodeTransform = lRootNode.GetParent().EvaluateGlobalTransform()

            lClusterGlobalInitMatrix = FbxAMatrix()
            lReferenceGlobalInitMatrix = FbxAMatrix()

            lT = pNode.GetGeometricTranslation(FbxNode.eSourcePivot)
            lR = pNode.GetGeometricRotation(FbxNode.eSourcePivot)
            lS = pNode.GetGeometricScaling(FbxNode.eSourcePivot)
            for i in range(len(lGLTFSkin['joints'])):
                lJointName = lGLTFSkin['joints'][i]
                lCluster = lClusters[lJointName]

                # Inverse Bind Pose Matrix
                # Matrix of Mesh
                lCluster.GetTransformMatrix(lReferenceGlobalInitMatrix)
                # Matrix of Joint
                lCluster.GetTransformLinkMatrix(lClusterGlobalInitMatrix)
                # http://blog.csdn.net/bugrunner/article/details/7232291
                # http://help.autodesk.com/view/FBX/2017/ENU/?guid=__cpp_ref__view_scene_2_draw_scene_8cxx_example_html
                m = lClusterGlobalInitMatrix.Inverse() * lReferenceGlobalInitMatrix * FbxAMatrix(lT, lR, lS)
                invBindMatricesBuffer.extend(struct.pack('<'+'f' * 16,  m[0][0], m[0][1], m[0][2], m[0][3], m[1][0], m[1][1], m[1][2], m[1][3], m[2][0], m[2][1], m[2][2], m[2][3], m[3][0], m[3][1], m[3][2], m[3][3]))
                lGLTFSkin['inverseBindMatrices']['count'] += 1

            for i in range(len(lExtraJoints)):
                invBindMatricesBuffer.extend(struct.pack('<'+'f' * 16, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))
                lGLTFSkin['inverseBindMatrices']['count'] += 1

            lGLTFSkin['joints'] += lExtraJoints

            # Mesh with skin should have identity global transform.
            # Since vertices have all been transformed to skeleton spaces.
            # PENDING
            m = FbxAMatrix()
            if not pNode.GetParent() == None:
                m = pNode.GetParent().EvaluateGlobalTransform(pPoseTime)
            m = m.Inverse()
            lGLTFNode['matrix'] = [
                m[0][0], m[0][1], m[0][2], m[0][3], m[1][0], m[1][1], m[1][2], m[1][3], m[2][0], m[2][1], m[2][2], m[2][3], m[3][0], m[3][1], m[3][2], m[3][3]
            ]
        else:
            lGLTFNode['meshes'] = [lMeshKey]

    else:
        # Camera and light node attribute
        lNodeAttribute = pNode.GetNodeAttribute()
        if not lNodeAttribute == None:
            lAttributeType = lNodeAttribute.GetAttributeType()
            if lAttributeType == FbxNodeAttribute.eCamera:
                lCameraKey = ConvertCamera(lNodeAttribute)
                lGLTFNode['camera'] = lCameraKey
            elif lAttributeType == FbxNodeAttribute.eLight:
                lLightKey = ConvertLight(lNodeAttribute)
                lGLTFNode['lights'] = [lLightKey]
            elif lAttributeType == FbxNodeAttribute.eSkeleton:
                # Use node name as joint id
                lGLTFNode['jointId'] = lNodeName
                lib_joints[lNodeName] = lGLTFNode

    lGLTFNode['children'] = []
    for i in range(pNode.GetChildCount()):
        lChildNodeName = ConvertSceneNode(pScene, pNode.GetChild(i), pPoseTime, fbxConverter)
        lGLTFNode['children'].append(lChildNodeName)

    return lNodeName

def ConvertScene(pScene, pPoseTime, fbxConverter):
    lRoot = pScene.GetRootNode()

    lSceneName = pScene.GetName()
    if lSceneName == "":
        lSceneName = "scene_" + str(len(lib_scenes.keys()))

    lGLTFScene = lib_scenes[lSceneName] = {"nodes" : []}

    for i in range(lRoot.GetChildCount()):
        lNodeName = ConvertSceneNode(pScene, lRoot.GetChild(i), pPoseTime, fbxConverter)
        lGLTFScene['nodes'].append(lNodeName)

    return lSceneName

def CreateAnimation():
    lAnimName = 'ani_' + str(len(lib_animations.keys()))
    lGLTFAnimation = {
        'channels' : [],
        'count' : 0,
        'parameters' : {},
        'samplers' : {}
    }

    return lAnimName, lGLTFAnimation

_samplerChannels = ['rotation', 'scale', 'translation']

def GetPropertyAnimationCurveTime(pAnimCurve):
    lTimeSpan = FbxTimeSpan()
    pAnimCurve.GetTimeInterval(lTimeSpan)
    lStartTimeDouble = lTimeSpan.GetStart().GetSecondDouble()
    lEndTimeDouble = lTimeSpan.GetStop().GetSecondDouble()
    lDuration = lEndTimeDouble - lStartTimeDouble

    return lStartTimeDouble, lEndTimeDouble, lDuration

def ConvertNodeAnimation(pAnimLayer, pNode, pSampleRate, pStartTime, pDuration):
    lNodeName = GetNodeNameWithoutDuplication(pNode)

    # PENDING
    lTranslationCurve = pNode.LclTranslation.GetCurve(pAnimLayer, 'X')
    lRotationCurve = pNode.LclRotation.GetCurve(pAnimLayer, 'X')
    lScalingCurve = pNode.LclScaling.GetCurve(pAnimLayer, 'X')

    lHaveTranslation = not lTranslationCurve == None
    lHaveRotation = not lRotationCurve == None
    lHaveScaling = not lScalingCurve == None

    # Curve time span may much smaller than stack local time span
    # It can reduce a lot of space
    # PENDING
    lStartTimeDouble = lEndTimeDouble = lDuration = 0
    if lHaveTranslation:
        lStartTimeDouble, lEndTimeDouble, lDuration = GetPropertyAnimationCurveTime(lTranslationCurve)

    if lDuration < 1e-5 and lHaveRotation:
        lStartTimeDouble, lEndTimeDouble, lDuration = GetPropertyAnimationCurveTime(lRotationCurve)

    if lDuration < 1e-5 and lHaveScaling:
        lStartTimeDouble, lEndTimeDouble, lDuration = GetPropertyAnimationCurveTime(lScalingCurve)

    lDuration = min(lDuration, pDuration)
    lStartTimeDouble = max(lStartTimeDouble, pStartTime)

    if lDuration > 1e-5:
        lAnimName, lGLTFAnimation = CreateAnimation()

        lNumFrames = math.ceil(lDuration / pSampleRate)

        lTime = FbxTime()

        lTimeChannel = []
        lTranslationChannel = []
        lRotationChannel = []
        lScaleChannel = []

        lQuaternion = FbxQuaternion()
        for i in range(lNumFrames):
            lSecondDouble = min(lStartTimeDouble + pSampleRate * i, lEndTimeDouble)
            lTime.SetSecondDouble(lSecondDouble)

            lTransform = pNode.EvaluateLocalTransform(lTime)
            lTranslation = lTransform.GetT()
            lQuaternion = lTransform.GetQ()
            lScale = lTransform.GetS()

            #Convert quaternion to axis angle
            lTimeChannel.append(lSecondDouble)

            if lHaveRotation:
                lRotationChannel.append(QuaternionToAxisAngle(lQuaternion))
            if lHaveTranslation:
                lTranslationChannel.append(list(lTranslation))
            if lHaveScaling:
                lScaleChannel.append(list(lScale))

        lGLTFAnimation['count'] = lNumFrames
        lGLTFAnimation['parameters']['TIME'] = CreateAnimationBuffer(lTimeChannel, 'f', 1)
        if lHaveTranslation:
            lGLTFAnimation['parameters']['translation'] = CreateAnimationBuffer(lTranslationChannel, 'f', 3)
        if lHaveRotation:
            lGLTFAnimation['parameters']['rotation'] = CreateAnimationBuffer(lRotationChannel, 'f', 4)
        if lHaveScaling:
            lGLTFAnimation['parameters']['scale'] = CreateAnimationBuffer(lScaleChannel, 'f', 3)

        #TODO Other interpolation methods
        for path in _samplerChannels:
            if path in lGLTFAnimation['parameters']:
                lSamplerName = lAnimName + '_' + path[0:3]
                lGLTFAnimation['samplers'][lSamplerName] = {
                    "input": "TIME",
                    "interpolation": "LINEAR",
                    "output": path
                }
                lGLTFAnimation['channels'].append({
                    "sampler" : lSamplerName,
                    "target" : {
                        "id" : lNodeName,
                        "path" : path
                    }
                })

        if len(lGLTFAnimation['channels']) > 0:
            lib_animations[lAnimName] = lGLTFAnimation

    for i in range(pNode.GetChildCount()):
        ConvertNodeAnimation(pAnimLayer, pNode.GetChild(i), pSampleRate, pStartTime, pDuration)

def ConvertAnimation(pScene, pSampleRate, pStartTime, pDuration):
    lRoot = pScene.GetRootNode()
    for i in range(pScene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))):
        lAnimStack = pScene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)
        for j in range(lAnimStack.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimLayer.ClassId))):
            lAnimLayer = lAnimStack.GetSrcObject(FbxCriteria.ObjectType(FbxAnimLayer.ClassId), j)
            # for k in range(lRoot.GetChildCount()):
            ConvertNodeAnimation(lAnimLayer, lRoot, pSampleRate, pStartTime, pDuration)

def CreateBufferViews(pBufferName):
    lByteOffset = 0

    lBufferViewNamePrefix = 'bv_'

    #Attribute buffer view
    lBufferViewName = lBufferViewNamePrefix + str(GetId())
    lBufferView = lib_buffer_views[lBufferViewName] = {}
    lBufferView['buffer'] = pBufferName
    lBufferView['byteLength'] = len(attributeBuffer)
    lBufferView['byteOffset'] = lByteOffset
    lBufferView['target'] = GL_ARRAY_BUFFER

    for lKey, lAttrib in lib_attributes.items():
        lAttrib['bufferView'] = lBufferViewName
        lib_accessors[lKey] = lAttrib

    lByteOffset += lBufferView['byteLength']

    #Inverse Bind Pose Matrices
    if len(invBindMatricesBuffer) > 0:
        lBufferViewName = lBufferViewNamePrefix + str(GetId())
        lBufferView = lib_buffer_views[lBufferViewName] = {}
        lBufferView['buffer'] = pBufferName
        lBufferView['byteLength'] = len(invBindMatricesBuffer)
        lBufferView['byteOffset'] = lByteOffset

        for lSkin in lib_skins.values():
            lSkin['inverseBindMatrices']['bufferView'] = lBufferViewName

        lByteOffset += lBufferView['byteLength']

    #Animations
    if len(animationBuffer) > 0:
        lBufferViewName = lBufferViewNamePrefix + str(GetId())
        lBufferView = lib_buffer_views[lBufferViewName] = {}
        lBufferView['buffer'] = pBufferName
        lBufferView['byteLength'] = len(animationBuffer)
        lBufferView['byteOffset'] = lByteOffset

        for lKey, lAccessor in lib_parameters.items():
            lAccessor['bufferView'] = lBufferViewName
            lib_accessors[lKey] = lAccessor

        lByteOffset += lBufferView['byteLength']

    #Indices buffer view
    #Put the indices buffer at last or there may be a error
    #When creating a Float32Array, which the offset must be multiple of 4
    lBufferViewName = lBufferViewNamePrefix + str(GetId())
    lBufferView = lib_buffer_views[lBufferViewName] = {}
    lBufferView['buffer'] = pBufferName
    lBufferView['byteLength'] = len(indicesBuffer)
    lBufferView['byteOffset'] = lByteOffset
    lBufferView['target'] = GL_ELEMENT_ARRAY_BUFFER

    for lKey, lIndices in lib_indices.items():
        lIndices['bufferView'] = lBufferViewName
        lib_accessors[lKey] = lIndices

    lByteOffset += lBufferView['byteLength']

def ListNodes(pNode):
    fbxNodes[GetNodeNameWithoutDuplication(pNode)] = pNode
    for k in range(pNode.GetChildCount()):
        ListNodes(pNode.GetChild(k))

# FIXME
# http://help.autodesk.com/view/FBX/2017/ENU/?guid=__cpp_ref_fbxtime_8h_html
TIME_INFINITY = FbxTime(0x7fffffffffffffff)

def Convert(
    filePath,
    ouptutFile = '',
    excluded = [],
    animFrameRate = 1 / 20,
    startTime = 0,
    duration = 1000,
    poseTime = TIME_INFINITY):

    ignoreScene = 'scene' in excluded
    ignoreAnimation = 'animation' in excluded
    # Prepare the FBX SDK.
    lSdkManager, lScene = InitializeSdkObjects()
    fbxConverter = FbxGeometryConverter(lSdkManager)
    # Load the scene.
    lResult = LoadScene(lSdkManager, lScene, filePath)

    if not lResult:
        print("\n\nAn error occurred while loading the scene...")
    else:
        lBasename, lExt = os.path.splitext(ouptutFile)

        ListNodes(lScene.GetRootNode())
        if not ignoreScene:
            lSceneName = ConvertScene(lScene, poseTime, fbxConverter)
        if not ignoreAnimation:
            ConvertAnimation(lScene, animFrameRate, startTime, duration)

        #Merge binary data and write to a binary file
        lBin = bytearray()
        lBin.extend(attributeBuffer)
        lBin.extend(invBindMatricesBuffer)
        lBin.extend(animationBuffer)
        lBin.extend(indicesBuffer)

        out = open(lBasename + ".bin", 'wb')
        out.write(lBin)
        out.close()

        lBufferName = lBasename + '.bin'
        lib_buffers[lBufferName] = {'byteLength' : len(lBin), 'path' : os.path.basename(lBufferName)}

        CreateBufferViews(lBufferName)

        #Output json
        lOutput = {
            'animations' : lib_animations,
            'asset' : {},
            'shaders' : {},
            'accessors' : lib_accessors,
            'bufferViews' : lib_buffer_views,
            'buffers' : lib_buffers,
            'textures' : lib_textures,
            'samplers' : lib_samplers,
            'images' : lib_images,
            'materials' : lib_materials,
            'techniques' : lib_techniques,
            'nodes' : lib_nodes,
            'cameras' : lib_cameras,
            'lights' : lib_lights,
            'scenes' : lib_scenes,
            'meshes' : lib_meshes,
            'skins' : lib_skins,
        }
        #Default scene
        if not ignoreScene:
            lOutput['scene'] = lSceneName

        out = open(ouptutFile, 'w')
        out.write(json.dumps(lOutput, indent = 2, sort_keys = True, separators=(',', ': ')))
        out.close()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='FBX to glTF converter', add_help=True)
    parser.add_argument('-e', '--exclude', type=str, default='', help="Data excluded. Can be: scene,animation")
    parser.add_argument('-t', '--timerange', default='0,1000', type=str, help="Export animation time, in format 'startSecond,endSecond'")
    parser.add_argument('-o', '--output', default='', type=str, help="Ouput glTF file path")
    parser.add_argument('-f', '--framerate', default=20, type=float, help="Animation frame per sencond")
    parser.add_argument('-p', '--pose', default=-1, type=float, help="Static pose time")
    parser.add_argument('file')

    args = parser.parse_args()

    lPoseTime = TIME_INFINITY
    lStartTime = 0
    lDuration = 1000
    lTimeRange = args.timerange.split(',')
    if lTimeRange[0]:
        lStartTime = float(lTimeRange[0])
    if lTimeRange[1]:
        lDuration = float(lTimeRange[1])

    if not args.output:
        lBasename, lExt = os.path.splitext(args.file)
        args.output = lBasename + '.gltf'

    if (args.pose >= 0):
        lPoseTime = FbxTime()
        lPoseTime.SetSecondDouble(float(args.pose))

    excluded = args.exclude.split(',')

    Convert(args.file, args.output, excluded, 1 / args.framerate, lStartTime, lDuration, lPoseTime)